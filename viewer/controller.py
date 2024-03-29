import os
import time
import pickle
import pyqtgraph as pg
import pyqtgraph.exporters
import numpy as np
import pandas as pd
from zipfile import ZipFile
from PyQt6.QtGui import QShortcut, QKeySequence, QFont
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QFileDialog, QProgressBar, QApplication
from PyQt6.QtCore import pyqtSignal, QObject, Qt, QTimer, QThread

from viewer.datahandler import DataHandler
from viewer.pointcollectors import PointCollectionMode, TauCollectionMode
from viewer.settings import PyqtgraphSettings, PlottingStyles, SettingsFile, SettingsMenu
from viewer.video_viewer import VideoViewer
from viewer.video_converter import VideoConverter
from viewer.multi_trace_plot import MultiPlotScrollArea
from viewer.gui import ImportDataTracesWindow
# from IPython import embed


class MyTextItem(pg.TextItem):
    def __init__(self, name, *args, **kwargs):
        super(MyTextItem, self).__init__(*args, **kwargs)
        self.item_name = name

    def name(self):
        return self.item_name


class MyLinearRegionItem(pg.LinearRegionItem):
    sigDoubleClicked = pyqtSignal()

    def __init__(self, name, *args, **kwargs):
        super(MyLinearRegionItem, self).__init__(*args, **kwargs)
        self.item_name = name

    def name(self):
        return self.item_name

    def define_range(self):
        pos = self.startPositions

    def mouseClickEvent(self, ev):
        if ev.double():
            # print('DOUBLE')
            self.sigDoubleClicked.emit()
            pos1 = self.lines[0].value()
            self.setRegion((pos1, pos1+100))

        if self.moving and ev.button() == Qt.MouseButton.RightButton:
            ev.accept()
            for i, l in enumerate(self.lines):
                l.setPos(self.startPositions[i])
            self.moving = False
            self.sigRegionChanged.emit(self)
            self.sigRegionChangeFinished.emit(self)

    def hoverEvent(self, ev):
        if self.movable and (not ev.isExit()) and ev.acceptDrags(Qt.MouseButton.LeftButton):
            self.setMouseHover(True)
        else:
            self.setMouseHover(False)


class HoverableCurveItem(pg.PlotCurveItem):
    # SIGNALS
    sigCurveHovered = pyqtSignal(int, object)
    sigCurveNotHovered = pyqtSignal(int, object)
    sigCurveClicked = pyqtSignal(object, object)
    sigDeleteEvent = pyqtSignal(int)

    def __init__(self, data_name, event_id, hoverPen, hoverable=True, *args, **kwargs):
        super(HoverableCurveItem, self).__init__(*args, **kwargs)
        self.data_name = data_name
        self.event_id = event_id
        self.hoverable = hoverable
        self.setAcceptHoverEvents(True)
        self.pen = self.opts['pen']
        self.hoverPen = hoverPen

    def hoverEvent(self, ev):
        if self.hoverable:
            try:
                pos = ev.pos()
                if self.mouseShape().contains(pos):
                    # self.sigCurveHovered.emit(self, ev, self.data_name)
                    self.sigCurveHovered.emit(self.event_id, ev)
                    self.setPen(self.hoverPen)
                    # self.setShadowPen(self.hoverShadowPen)
                else:
                    self.sigCurveNotHovered.emit(self.event_id, ev)
                    self.setPen(self.pen)
                    # self.setShadowPen(None)
            except AttributeError:
                self.setPen(self.pen)

    @staticmethod
    def delete_dialog():
        msg_box = QMessageBox()
        msg_box.setText('Delete Event ...')
        msg_box.setInformativeText('Do you want to delete this event?')
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
        retval = msg_box.exec()
        return retval

    def mouseClickEvent(self, ev):
        if self.mouseShape().contains(ev.pos()):
            self.sigCurveClicked.emit(self, ev)
            if ev.button() == Qt.MouseButton.LeftButton:
                retval = self.delete_dialog()
                if retval == QMessageBox.StandardButton.Yes:
                    self.sigDeleteEvent.emit(self.event_id)
                    self.pen = None
                    self.hoverPen = None
                    self.setPen(self.pen)


class Controller(QObject):
    # ==================================================================================================================
    # SIGNALS
    # ------------------------------------------------------------------------------------------------------------------
    signal_import_traces = pyqtSignal()
    signal_roi_changed = pyqtSignal()

    # ==================================================================================================================
    # INITIALIZING
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, gui):
        QObject.__init__(self)
        # Create GUI
        self.gui = gui
        self.gui.closeEvent = self.closeEvent

        # Check Settings
        self.settings_file = SettingsFile()

        # Create Video Viewer
        # self.video_viewer = VideoViewer()
        self.video_viewer = VideoViewer()
        # self.video_viewer = VideoViewerQT()
        self.video_match = False
        self.video_connected = False
        self.video_time_line = None
        self.video_time_line_stimulus = None

        # Create Video Converter
        self.video_converter = VideoConverter(self.settings_file)

        self.plot_design()
        self.connections()
        self._create_short_cuts()
        self._connect_short_cuts(connect=True)
        self.event_plots = []
        self.stimulus_onsets_visible = False
        self.stimulus_info_box_visible = False
        self.show_fbs = False

        # Cut Out Regions (pyqtgraph: LinearRegion)
        self.linear_region = None

        # KeyBoard Bindings
        self.gui.key_pressed.connect(self.on_key_press)
        self.gui.key_released.connect(self.on_key_release)
        self.gui.trace_plot_item.scene().sigMouseMoved.connect(self.mouse_moved)

        self.filter_locked = True
        self.filter_is_active = False
        self._start_new_session()
        # self.data_handler.signal_new_data.emit()

        # Stimulus Reconstruction dt
        self.stimulus_dt = 0.001
        self.multi_plotter = None

        self.get_sampling_rate_window = None

    def _start_new_session(self):
        self.gui.info_label.setText('Please Open Data File ...')
        self.clear_plots()
        self.event_plots = []
        self.show_fbs = False
        self.stimulus_onsets_visible = False
        self.stimulus_info_box_visible = False
        self.event_text = None
        self.data_handler = DataHandler()
        self.signals()
        self.filter_locked = True
        self.filter_is_active = False
        self.gui.filter_locK_button.setDisabled(True)
        self.gui.filter_slider.setDisabled(True)
        self.data_handler.data_norm_mode = 'raw'
        self.point_collection = PointCollectionMode(
            plot_window=self.gui.plot_graphics_layout_widget,
            plot_item=self.gui.trace_plot_item,

        )
        self.tau_collection = TauCollectionMode(
            plot_window=self.gui.plot_graphics_layout_widget,
            plot_item=self.gui.trace_plot_item,
        )
        self.pyqtgraph_settings = PyqtgraphSettings()
        self.freeze_gui(freeze=True, menu=False)
        self.gui.toolbar_show_stimulus.setDisabled(True)
        self.gui.toolbar_show_stimulus_info.setDisabled(True)
        self.gui.toolbar_fbs_trace_action.setDisabled(True)
        self.gui.toolbar_save_figure.setDisabled(True)

    def prepare_new_data(self):
        self.gui.info_label.setText('')
        self.gui.info_frame_rate.setText(f'Frame Rate: {self.data_handler.meta_data["sampling_rate"]:.3f} Hz')
        self.freeze_gui(freeze=False, menu=True)
        self.gui.filter_locK_button.setDisabled(True)
        self.gui.filter_slider.setDisabled(True)
        rois = np.array(self.data_handler.meta_data['roi_list']).astype(str)
        self.gui.roi_selection_combobox.clear()
        for k, r in zip(range(len(rois)), rois):
            self.gui.roi_selection_combobox.addItem(str(k))
            self.gui.roi_selection_combobox.setItemData(k, r)
        self.gui.roi_selection_combobox.activated.connect(self.roi_selected)
        self.gui.toolbar_show_stimulus.setDisabled(True)
        self.gui.toolbar_show_stimulus_info.setDisabled(True)
        self.gui.file_menu_action_save_csv.setDisabled(False)
        self.gui.file_menu_action_save_flags.setDisabled(False)
        self.gui.file_menu_action_save_viewer_file.setDisabled(False)
        self.gui.trace_plot_item.setLabel('left', 'Raw', **PlottingStyles.axis_label_styles)
        self.gui.toolbar_fbs_trace_action.setDisabled(False)
        self.gui.toolbar_save_figure.setDisabled(False)

    def plot_design(self):
        self.gui.trace_plot_item.setLabel('bottom', 'Time [s]', **PlottingStyles.axis_label_styles)
        self.gui.trace_plot_item.setLabel('left', 'Data', **PlottingStyles.axis_label_styles)

        pen = pg.mkPen(color=(0, 0, 0), width=PlottingStyles.axis_width)
        self.gui.trace_plot_item.getAxis("bottom").setPen(pen)
        self.gui.trace_plot_item.getAxis("bottom").setTextPen(pen)
        self.gui.trace_plot_item.getAxis("bottom").setTickPen(pen)

        self.gui.trace_plot_item.getAxis("left").setPen(pen)
        self.gui.trace_plot_item.getAxis("left").setTextPen(pen)
        self.gui.trace_plot_item.getAxis("left").setTickPen(pen)

        self.gui.stimulus_plot_item.getAxis("bottom").setPen(pen)
        self.gui.stimulus_plot_item.getAxis("bottom").setTextPen(pen)
        self.gui.stimulus_plot_item.getAxis("bottom").setTickPen(pen)

        self.gui.stimulus_plot_item.getAxis("left").setPen(pen)
        self.gui.stimulus_plot_item.getAxis("left").setTextPen(pen)
        self.gui.stimulus_plot_item.getAxis("left").setTickPen(pen)

        font = QFont()
        font.setPixelSize(PlottingStyles.axis_ticks_font_size)
        self.gui.trace_plot_item.getAxis("bottom").setTickFont(font)
        self.gui.trace_plot_item.getAxis("left").setTickFont(font)

        self.gui.stimulus_plot_item.getAxis("bottom").setTickFont(font)
        self.gui.stimulus_plot_item.getAxis("left").setTickFont(font)

    def signals(self):
        # self.data_handler.signal_roi_id_changed.connect(lambda: self.plot_traces(update_axis=True))
        self.data_handler.signal_roi_id_changed.connect(lambda: self.update_plot(update_axis=True))
        self.data_handler.signal_roi_id_changed.connect(self.disconnect_video)

    def connections(self):
        # File Menu
        self.gui.file_menu_action_new_session.triggered.connect(self._start_new_session)
        self.gui.file_menu_action_import_traces.triggered.connect(self.import_traces_from_csv)
        self.gui.file_menu_action_import_stimulus.triggered.connect(self.import_stimulus)
        # self.gui.file_menu_action_import_stimulus_trace.triggered.connect(self.import_single_trace)
        self.gui.file_menu_action_import_stimulus_trace.triggered.connect(self.import_extra_trace)

        self.gui.file_menu_action_import_meta_data.triggered.connect(self.import_meta_data)
        self.gui.file_menu_action_save_csv.triggered.connect(self.export_results)
        self.gui.file_menu_action_save_flags.triggered.connect(self.export_flags)
        self.gui.file_menu_action_open_viewer_file.triggered.connect(self._load_file)
        self.gui.file_menu_action_save_viewer_file.triggered.connect(self._save_file)
        self.gui.file_menu_action_settings.triggered.connect(self._edit_settings)
        self.gui.file_menu_action_exit.triggered.connect(self.gui.exit_app)

        # Tools Menu
        # Video Viewer
        self.gui.tools_menu_open_video_viewer.triggered.connect(self.open_video_viewer)
        self.video_viewer.FrameChanged.connect(self.plot_video_pos)
        self.video_viewer.ConnectToDataTrace.connect(self.connect_video_to_data_trace)

        # MultiPlot
        self.gui.tools_menu_multiplot.triggered.connect(self.multi_plot)

        # Video Converter
        self.gui.tools_menu_video_converter.triggered.connect(self.open_video_converter)

        # Navigation
        # Buttons
        self.gui.next_button.clicked.connect(self._next_roi)
        self.gui.prev_button.clicked.connect(self._prev_roi)

        # Toolbar Buttons
        self.gui.toolbar_raw_action.triggered.connect(self._set_to_raw)
        self.gui.toolbar_df_action.triggered.connect(self._set_to_df)
        self.gui.toolbar_z_score_action.triggered.connect(self._set_to_z_score)
        self.gui.toolbar_filter_action.triggered.connect(self.activate_filter)
        self.gui.toolbar_show_stimulus.triggered.connect(self.plot_stimulus_onsets)
        self.gui.toolbar_show_stimulus_info.triggered.connect(self.stimulus_info_box)
        self.gui.toolbar_fbs_trace_action.triggered.connect(self.toggle_base_line_trace)
        self.gui.toolbar_min_max_action.triggered.connect(self._set_to_min_max)
        self.gui.toolbar_save_figure.triggered.connect(self.collect_events_for_plotting)
        self.gui.toolbar_flag_roi.triggered.connect(self.flag_roi)
        # self.gui.toolbar_save_figure.triggered.connect(self.save_figure)

        # Filter
        self.gui.filter_locK_button.clicked.connect(self.lock_filter_slider)
        self.gui.filter_slider.valueChanged.connect(self.filter_slider_changed)
        self.gui.filter_slider.setDisabled(True)
        self.gui.filter_locK_button.setDisabled(True)

    def _create_short_cuts(self):
        self.shortcut_next_roi = QShortcut(QKeySequence('right'), self.gui)
        self.shortcut_prev_roi = QShortcut(QKeySequence('left'), self.gui)
        self.shortcut_import_csv = QShortcut(QKeySequence('ctrl+i'), self.gui)
        self.shortcut_export_results = QShortcut(QKeySequence('ctrl+e'), self.gui)
        self.shortcut_open_file = QShortcut(QKeySequence('ctrl+o'), self.gui)
        self.shortcut_save_file = QShortcut(QKeySequence('ctrl+s'), self.gui)
        self.shortcut_import_meta_data = QShortcut(QKeySequence('ctrl+m'), self.gui)
        self.shortcut_import_stimulus = QShortcut(QKeySequence('ctrl+b'), self.gui)
        self.shortcut_exit = QShortcut(QKeySequence('ctrl+q'), self.gui)
        self.shortcut_reset_axis = QShortcut(QKeySequence('R'), self.gui)
        self.shortcut_linear_region = QShortcut(QKeySequence('L'), self.gui)

    def _connect_short_cuts(self, connect=True):
        if connect:
            self.shortcut_next_roi.activated.connect(self._next_roi)
            self.shortcut_prev_roi.activated.connect(self._prev_roi)
            self.shortcut_import_csv.activated.connect(self.import_traces_from_csv)
            self.shortcut_export_results.activated.connect(self.export_results)
            self.shortcut_open_file.activated.connect(self._load_file)
            self.shortcut_save_file.activated.connect(self._save_file)
            self.shortcut_import_meta_data.activated.connect(self.import_meta_data)
            self.shortcut_import_stimulus.activated.connect(self.import_stimulus)
            self.shortcut_exit.activated.connect(self.gui.exit_app)
            self.shortcut_reset_axis.activated.connect(self.reset_axis)
            self.shortcut_linear_region.activated.connect(self.show_linear_region)
        else:
            self.shortcut_next_roi.activated.disconnect()
            self.shortcut_prev_roi.activated.disconnect()

    def disconnect_video(self):
        self.video_connected = False
        item_list = self.gui.trace_plot_item.items.copy()
        for item in item_list:
            if isinstance(item, pg.InfiniteLine):
                self.gui.trace_plot_item.removeItem(item)

        item_list = self.gui.stimulus_plot_item.items.copy()
        for item in item_list:
            if isinstance(item, pg.InfiniteLine):
                self.gui.stimulus_plot_item.removeItem(item)

        self.video_time_line = None
        self.video_time_line_stimulus = None
        self.video_viewer.connect_video_to_data_trace_button.setText('Connect to Data')

    def connect_video_to_data_trace(self, sig):
        self.video_connected = sig
        if not self.video_connected:
            item_list = self.gui.trace_plot_item.items.copy()
            for item in item_list:
                if isinstance(item, pg.InfiniteLine):
                    self.gui.trace_plot_item.removeItem(item)

            item_list = self.gui.stimulus_plot_item.items.copy()
            for item in item_list:
                if isinstance(item, pg.InfiniteLine):
                    self.gui.stimulus_plot_item.removeItem(item)

            self.video_time_line = None
            self.video_time_line_stimulus = None
        self.check_video()
        self.plot_video_pos()

    def _edit_settings(self):
        self.settings_menu = SettingsMenu(self.data_handler)
        self.settings_menu.show_menu()

    # ==================================================================================================================
    # PLOTTING
    # ------------------------------------------------------------------------------------------------------------------
    def progress_bar_update(self, val):
        QApplication.processEvents()
        self.progress.setValue(val)

    def multi_plot(self):
        if self.data_handler.data is not None:
            # Prepare Data
            data_set = self.data_handler.data.copy()
            data_traces = []
            for roi in data_set:
                data_traces.append(data_set[roi]['data_traces'][self.data_handler.data_norm_mode])

            # self.progress_win = QWidget()
            self.progress = QProgressBar()
            self.progress.setMaximum(len(data_traces))
            self.progress.setGeometry(400, 400, 250, 20)
            self.progress.show()

            self.multi_plotter = MultiPlotScrollArea(np.array(data_traces))
            self.multi_plotter.row_finished.connect(self.progress_bar_update)
            self.multi_plotter.start()
            self.multi_plotter.show()
            self.progress.close()

    def update_linear_region(self):
        fr = self.data_handler.meta_data['sampling_rate']
        region_vals = self.linear_region.getRegion()
        start_time = region_vals[0]
        end_time = region_vals[1]
        start_idx = int(start_time * fr)
        end_idx = int(end_time * fr)
        print(f'Time: from {start_time} s to {end_time} s')
        print(f'Samples: from {start_idx} to {end_idx}')
        cot_time, cot_vals = self.cut_out_trace(start_idx, end_idx, filtered=False)
        if self.filter_is_active:
            fcot_time, fcot_vals = self.cut_out_trace(start_idx, end_idx, filtered=True)

    def show_linear_region(self):
        if self.linear_region is None:
            self.plot_linear_region()
        else:
            self.remove_linear_region()

    def remove_linear_region(self):
        item_list = self.gui.trace_plot_item.items.copy()
        for item in item_list:
            if isinstance(item, pg.LinearRegionItem):
                self.gui.trace_plot_item.removeItem(item)
        self.linear_region = None

    def plot_linear_region(self):
        # Clear the plot
        # self.gui.trace_plot_item.clear()
        time_axis = self.data_handler.get_time_axis(self.data_handler.roi_id)
        # Add a LinearRegion for slicing data trace
        region_pen = pg.mkPen(color='g', width=2)
        # R, G, B, [A]
        region_color = pg.mkColor(100, 255, 100, 100)
        region_hover_color = pg.mkColor(255, 200, 200, 100)
        self.linear_region = MyLinearRegionItem(
            name='LinearRegion',
            values=[100, 500],
            pen=region_pen,
            brush=pg.mkBrush(color=region_color),
            hoverPen=region_pen,
            hoverBrush=pg.mkBrush(color=region_hover_color),
            bounds=[0, time_axis.max()],
            movable=True,
            swapMode='block',
            # clipItem=self.gui.trace_plot_item,
        )
        # self.linear_region.sigRegionChanged.connect(self.update_linear_region)
        self.linear_region.sigRegionChangeFinished.connect(self.update_linear_region)
        # self.linear_region.sigDoubleClicked.connect(self.linear_region_define_range)
        # region.setZValue(10)
        # Add the LinearRegionItem to the ViewBox, but tell the ViewBox to exclude this
        # item when doing auto-range calculations.
        self.gui.trace_plot_item.addItem(self.linear_region, ignoreBounds=True)
        # self.update_plot(update_axis=False, clear=False)

    def plot_extra_traces(self):
        if self.data_handler.data[self.data_handler.roi_id]:
            print('')

    def update_plot(self, update_axis=False, clear=True):
        # Clear the plot
        if clear:
            self.gui.trace_plot_item.clear()

        # Plot Data Trace
        self.gui.trace_plot_item.setTitle(f'ROI_{self.data_handler.roi_id}')
        time_axis = self.data_handler.get_time_axis(self.data_handler.roi_id)
        f_y = self.data_handler.data[self.data_handler.roi_id]['data_traces'][self.data_handler.data_norm_mode]

        if self.filter_is_active:
            trace_pen = PlottingStyles.line_pen_transparent
        else:
            trace_pen = PlottingStyles.line_pen

        plot_data_item = pg.PlotDataItem(
            time_axis, f_y,
            pen=trace_pen,
            # name=f'{self.data_handler.data_name}_ROI{self.data_handler.roi_id}',
            name=f'data_trace',
            skipFiniteCheck=True,
            tip=None,
        )
        self.gui.trace_plot_item.addItem(plot_data_item)

        if update_axis:
            self._update_axis_limits(time_axis=time_axis)

        # Plot Filtered Trace
        if self.filter_is_active:
            self.data_handler.moving_average_filter()
            time_axis = self.data_handler.get_time_axis(self.data_handler.roi_id)
            f_y = self.data_handler.data[self.data_handler.roi_id]['data_traces']['filtered']
            plot_data_item = pg.PlotDataItem(
                time_axis, f_y,
                pen=pg.mkPen(color='r'),
                # name=f'{self.data_handler.data_name}_ROI{self.data_handler.roi_id}',
                name=f'filtered_trace',
                skipFiniteCheck=True,
                tip=None,
            )
            self.gui.trace_plot_item.addItem(plot_data_item)

        # Plot Stimulus
        if self.stimulus_onsets_visible:
            y_min, y_max = self.get_max_data_values()
            k = 0
            for start in self.data_handler.meta_data['stimulus']['start']:
                plot_stimulus = pg.PlotDataItem(
                    [start, start], [y_min, y_max],
                    pen=pg.mkPen(color='b', width=1),
                    skipFiniteCheck=True,
                    name=f'stimulus_onset_{k}',
                    tip=None,
                )

                self.gui.trace_plot_item.addItem(plot_stimulus)
                k += 1

            # Plot Stimulus Info Box
            if self.stimulus_info_box_visible:
                self.show_stimulus_info_box()

        # Plot Events
        if self.data_handler.get_events_count(self.data_handler.roi_id) > 0:
            self.event_plots = []
            events = self.data_handler.get_roi_events(self.data_handler.roi_id)
            for key in events:
                t, f_y = self.cut_out_trace(start_idx=events[key]['start_idx'], end_idx=events[key]['end_idx'])
                # plot_data_item = pg.PlotDataItem(
                #     t, f_y,
                #     pen=pg.mkPen(color=events[key]['pen_color']),
                #     name=f'{key}_trace',
                #     skipFiniteCheck=True,
                #     tip=None,
                # )
                plot_data_item = HoverableCurveItem(
                    x=t,
                    y=f_y,
                    name=f'event_{key}',
                    pen=pg.mkPen(color=events[key]['pen_color'], width=1),
                    hoverPen=pg.mkPen(color=events[key]['hover_pen_color'], width=2),
                    data_name=f'event_{key}',
                    event_id=key,
                )

                self.gui.trace_plot_item.addItem(plot_data_item)
                self.event_plots.append(plot_data_item)
                plot_data_item.sigDeleteEvent.connect(self.remove_event)
                plot_data_item.sigCurveHovered.connect(self.show_event_info_box)
                plot_data_item.sigCurveNotHovered.connect(self.hide_event_info_box)

                if self.filter_is_active:
                    # Filtered trace
                    t2, f_y2 = self.cut_out_trace(start_idx=events[key]['start_idx'], end_idx=events[key]['end_idx'],
                                                  filtered=True)
                    # plot_data_item2 = HoverableCurveItem(
                    #     x=t2,
                    #     y=f_y2,
                    #     name=f'event_{key}',
                    #     pen=pg.mkPen(color=events[key]['pen_darker_color'], width=3),
                    #     hoverPen=pg.mkPen(color=events[key]['hover_pen_color'], width=8),
                    #     data_name=f'event_{key}',
                    #     event_id=key,
                    # )

                    plot_data_item2 = pg.PlotDataItem(
                        t2, f_y2,
                        pen=pg.mkPen(color=events[key]['pen_darker_color']),
                        name=f'{key}_trace',
                        skipFiniteCheck=True,
                        tip=None,
                    )

                    # plot_data_item2.setClickable(True)
                    self.gui.trace_plot_item.addItem(plot_data_item2)
                    self.event_plots.append(plot_data_item2)
                    # plot_data_item2.sigDeleteEvent.connect(self.remove_event)
                    # plot_data_item2.sigCurveHovered.connect(self.show_event_info_box)
                    # plot_data_item2.sigCurveNotHovered.connect(self.hide_event_info_box)
                self.plot_exp_fits()

                # Plot the Points
                p1_idx = 0
                p2_idx = events[key]['center_idx']-events[key]['start_idx']
                p3_idx = -1
                p1_t = events[key]['p1_t']
                p2_t = events[key]['p2_t']
                p3_t = events[key]['p3_t']
                points_t = [p1_t, p2_t, p3_t]
                if self.filter_is_active:
                    p1_y = f_y2[p1_idx]
                    p2_y = f_y2[p2_idx]
                    p3_y = f_y2[p3_idx]
                else:
                    p1_y = f_y[p1_idx]
                    p2_y = f_y[p2_idx]
                    p3_y = f_y[p3_idx]
                points_y = [p1_y, p2_y, p3_y]

                plot_data_item = pg.ScatterPlotItem(
                    points_t, points_y,
                    symbol='d',
                    pen=pg.mkPen(color='b', width=2),
                    brush=pg.mkBrush(color='g'),
                    size=15,
                    name=f'{key}_points',
                    skipFiniteCheck=True,
                    tip=None,
                )
                self.gui.trace_plot_item.addItem(plot_data_item)

        if self.show_fbs:
            if self.data_handler.data_norm_mode == 'raw':
                # fbs_trace = np.zeros_like(time_axis) + self.data_handler.data[self.data_handler.roi_id]['data_traces']['fbs']
                fbs_trace = [self.data_handler.data[self.data_handler.roi_id]['data_traces']['fbs'], self.data_handler.data[self.data_handler.roi_id]['data_traces']['fbs']]
            else:
                fbs_trace = [0, 0]

            time_points = [np.min(time_axis), np.max(time_axis)]
            plot_data_item = pg.PlotDataItem(
                time_points, fbs_trace,
                pen=pg.mkPen(color='g', width=3),
                name=f'base_line',
                skipFiniteCheck=True,
                tip=None,
            )
            self.gui.trace_plot_item.addItem(plot_data_item)

        # Plot ROI Single Traces (e.g. stimulus traces)
        self.plot_single_traces()

    def plot_video_pos(self):
        # check if there is already a plotted video point
        item_list = self.gui.trace_plot_item.items.copy()
        for item in item_list:
            if item.name() == 'video_point':
                self.gui.trace_plot_item.removeItem(item)

        if self.video_viewer.isEnabled() and self.video_connected and self.data_handler.data is not None:
            self.check_video()
            if self.video_match:
                current_video_frame = self.video_viewer.current_frame
                # time_axis = self.data_handler.get_time_axis(self.data_handler.roi_id)
                if self.filter_is_active:
                    y_data = self.data_handler.data[self.data_handler.roi_id]['data_traces']['filtered']
                else:
                    y_data = self.data_handler.data[self.data_handler.roi_id]['data_traces'][self.data_handler.data_norm_mode]
                # Get current video frame
                y_point = y_data[current_video_frame]
                current_video_time = current_video_frame / self.data_handler.meta_data['sampling_rate']
                print(f'video time: {current_video_time}')
                # Plot the current Time Point on the data trace
                scatter_item = pg.ScatterPlotItem(
                    [current_video_time], [y_point],
                    symbol='o',
                    pen=pg.mkPen(color='r', width=2),
                    brush=pg.mkBrush(color='r'),
                    size=15,
                    name=f'video_point',
                    skipFiniteCheck=True,
                    tip=None,
                )
                self.gui.trace_plot_item.addItem(scatter_item)
                if self.video_time_line is None:
                    # Plot a Time Line to the data trace and stimulus plot
                    self.video_time_line = pg.InfiniteLine(angle=90, movable=False, pen=PlottingStyles.time_line_pen)
                    self.video_time_line_stimulus = pg.InfiniteLine(angle=90, movable=False, pen=PlottingStyles.time_line_pen)
                    self.gui.trace_plot_item.addItem(self.video_time_line, ignoreBounds=True)
                    self.gui.stimulus_plot_item.addItem(self.video_time_line_stimulus, ignoreBounds=True)
                    self.video_time_line.setPos(current_video_time)
                    self.video_time_line_stimulus.setPos(current_video_time)
                else:
                    self.video_time_line.setPos(current_video_time)
                    self.video_time_line_stimulus.setPos(current_video_time)

                # check if there is already a plotted video point
                item_list = self.gui.stimulus_plot_item.items.copy()
                for item in item_list:
                    if item.name() == 'video_point':
                        self.gui.stimulus_plot_item.removeItem(item)
                if 'stimulus_trace' in self.data_handler.data[self.data_handler.roi_id]:
                    if len(self.data_handler.data[self.data_handler.roi_id]['stimulus_trace']) > 0:
                        d = self.data_handler.data[self.data_handler.roi_id]['stimulus_trace']['Values']
                        try:
                            stimulus_dt = self.data_handler.meta_data['single_trace_dt']
                        except IndexError:
                            stimulus_dt = float(self.settings_file.settings_file.get('stimulus_sampling_dt'))
                        current_sample = int(current_video_time / stimulus_dt)
                        y_point = d[current_sample]
                        scatter_item2 = pg.ScatterPlotItem(
                            [current_video_time], [y_point],
                            symbol='o',
                            pen=pg.mkPen(color='r', width=2),
                            brush=pg.mkBrush(color='r'),
                            size=15,
                            name=f'video_point',
                            skipFiniteCheck=True,
                            tip=None,
                        )
                        self.gui.stimulus_plot_item.addItem(scatter_item2)

    def clear_plots(self):
        self.gui.trace_plot_item.clear()
        self.gui.stimulus_plot_item.clear()

    def reset_axis(self):
        if self.data_handler.data is not None:
            self._update_axis_limits(time_axis=self.data_handler.get_time_axis(self.data_handler.roi_id))

    def _update_axis_limits(self, time_axis):
        # Get min and max values of all rois
        y_min, y_max = self.get_max_data_values()

        # Reset Axis
        self.gui.trace_plot_item.setXRange(0, np.max(time_axis), padding=0)
        self.gui.trace_plot_item.setYRange(y_min, y_max, padding=0)

    def hide_event_info_box(self, event_id, ev):
        event_name = f'{event_id}_info_box'
        item_list = self.gui.trace_plot_item.items.copy()
        for item in item_list:
            # if not isinstance(item, pg.TextItem):
            if item.name() == event_name:
                self.gui.trace_plot_item.removeItem(item)
        self.event_text = None

    def show_event_info_box(self, event_id, ev):
        if self.event_text is None:
            pos = ev.pos()
            event_name = f'{event_id}_info_box'
            event = self.data_handler.get_event(self.data_handler.roi_id, event_id)

            if event is not None:
                text = f'Event {event_id}: \n' \
                       f'tau rise: {event["tau_rise"]:.3f} s \n' \
                       f'tau decay: {event["tau_decay"]:.3f} s \n' \
                       f'fit rise: {event["fit_rise_tau"]:.3f} ({event["fit_rise_error"]:.3f}) s \n' \
                       f'fit decay: {event["fit_decay_tau"]:3f} ({event["fit_decay_error"]:.3f}) s'

                self.event_text = MyTextItem(
                    name=event_name,
                    text=text,
                    color='k',
                    border=pg.mkPen(color='k'),
                    fill=pg.mkBrush(color='w'),
                )
                self.gui.trace_plot_item.addItem(self.event_text)
                self.event_text.setPos(pos[0], pos[1])

    def plot_exp_fits(self):
        # # check if there is already a plotted trace
        # item_list = self.gui.trace_plot_item.items.copy()
        # for item in item_list:
        #     if item.name().startswith('Fit_'):
        #         self.gui.trace_plot_item.removeItem(item)

        events = self.data_handler.get_roi_events(roi_id=self.data_handler.roi_id)
        for event, event_id in zip(events.values(), events):
            # Cut out the event trace
            cut_rise_time, cut_rise_y = self.cut_out_trace(
                start_idx=event['start_idx'], end_idx=event['center_idx'], filtered=self.filter_is_active)
            cut_decay_time, cut_decay_y = self.cut_out_trace(
                start_idx=event['center_idx'], end_idx=event['end_idx'], filtered=self.filter_is_active)

            # Get the first time point
            t0_rise = np.min(cut_rise_time)
            t0_decay = np.min(cut_decay_time)

            # Normalize x and y values to fit data range
            rise_exp_t = event['fit_rise_time'] + t0_rise
            decay_exp_t = event['fit_decay_time'] + t0_decay
            rise_exp_y = event['fit_rise_y'] * (np.max(cut_rise_y) - np.min(cut_rise_y)) + np.min(cut_rise_y)
            decay_exp_y = event['fit_decay_y'] * (np.max(cut_decay_y) - np.min(cut_decay_y)) + np.min(cut_decay_y)

            rise_plot = pg.PlotDataItem(
                x=rise_exp_t, y=rise_exp_y,
                pen=PlottingStyles.fit_rise_pen,
                shadowPen=PlottingStyles.fit_rise_shadow_pen,
                name=f'Fit_Rise_{event_id}',
                tip=None,
                skipFiniteCheck=True
            )
            decay_plot = pg.PlotDataItem(
                x=decay_exp_t, y=decay_exp_y,
                pen=PlottingStyles.fit_decay_pen,
                shadowPen=PlottingStyles.fit_decay_shadow_pen,
                name=f'Fit_Decay_{event_id}',
                tip=None,
                skipFiniteCheck=True
            )
            self.gui.trace_plot_item.addItem(rise_plot)
            self.gui.trace_plot_item.addItem(decay_plot)
            self.event_plots.append(rise_plot)
            self.event_plots.append(decay_plot)

    def hide_stimulus_info_box(self):
        item_list = self.gui.trace_plot_item.items.copy()
        for item in item_list:
            if item.name().startswith('stimulus_info'):
                self.gui.trace_plot_item.removeItem(item)

    def show_stimulus_info_box(self):
        y_min, y_max = self.get_max_data_values()
        stimulus_info = self.data_handler.meta_data['stimulus']['info']
        time_points = self.data_handler.meta_data['stimulus']['start']
        for text, pos_x in zip(stimulus_info, time_points):
            event_text = MyTextItem(
                name=f'stimulus_info_{text}',
                text=str(text),
                color='k',
                border=pg.mkPen(color='k'),
                fill=pg.mkBrush(color='w'),
            )
            self.gui.trace_plot_item.addItem(event_text)
            event_text.setPos(pos_x, y_max)

    def stimulus_info_box(self):
        if self.stimulus_info_box_visible:
            self.hide_stimulus_info_box()
            self.gui.toolbar_show_stimulus_info.setText('Show Stimulus Info')
        else:
            self.show_stimulus_info_box()
            self.gui.toolbar_show_stimulus_info.setText('Hide Stimulus Info')

        # Flip switch
        self.stimulus_info_box_visible = np.invert(self.stimulus_info_box_visible)

    def plot_stimulus_onsets(self):
        if self.stimulus_onsets_visible:
            self.gui.toolbar_show_stimulus.setText('Show Stimulus')
            # Remove Stimulus Onsets
            item_list = self.gui.trace_plot_item.items.copy()
            for item in item_list:
                if item.name().startswith('stimulus_onset'):
                    self.gui.trace_plot_item.removeItem(item)
        else:
            # Plot Stimulus Onset
            # stimulus_info = self.data_handler.meta_data['stimulus']['info']
            self.gui.toolbar_show_stimulus.setText('Hide Stimulus')
            y_min, y_max = self.get_max_data_values()
            k = 0
            for start in self.data_handler.meta_data['stimulus']['start']:
                plot_stimulus = pg.PlotDataItem(
                    [start, start], [y_min, y_max],
                    pen=pg.mkPen(color='b', width=1),
                    skipFiniteCheck=True,
                    name=f'stimulus_onset_{k}',
                    tip=None,
                )

                self.gui.trace_plot_item.addItem(plot_stimulus)
                k += 1

        # Flip the switch
        self.stimulus_onsets_visible = np.invert(self.stimulus_onsets_visible)

    def plot_single_traces(self):
        # PLOT SINGLE TRACES
        # check if there are single traces plotted
        item_list = self.gui.stimulus_plot_item.items.copy()
        for item in item_list:
            if item.name() == 'single_trace':
                self.gui.stimulus_plot_item.removeItem(item)

        if 'stimulus_trace' in self.data_handler.data[self.data_handler.roi_id]:
            if len(self.data_handler.data[self.data_handler.roi_id]['stimulus_trace']) > 0:
                # d = self.data_handler.single_traces[self.data_handler.roi_id]
                d = self.data_handler.data[self.data_handler.roi_id]['stimulus_trace']['Values']
                t = self.data_handler.data[self.data_handler.roi_id]['stimulus_trace']['Time']
                plot_data_item = pg.PlotDataItem(
                    t, d,
                    pen=PlottingStyles.single_trace_pen,
                    name=f'single_trace',
                    skipFiniteCheck=True,
                    tip=None,
                )
                # Get min and max values of all rois
                y_min, y_max = np.min(d), np.max(d)

                # Reset Axis
                # self.gui.trace_plot_item.setXRange(0, np.max(time_axis), padding=0)
                self.gui.stimulus_plot_item.setYRange(y_min, y_max, padding=0)
                self.gui.stimulus_plot_item.addItem(plot_data_item)

    def plot_stimulus(self):
        # check if there is already a plotted trace
        item_list = self.gui.stimulus_plot_item.items.copy()
        for item in item_list:
            if item.name() == 'stimulus_trace':
                self.gui.stimulus_plot_item.removeItem(item)

        if self.data_handler.meta_data['stimulus']['available']:
            plot_data_item = pg.PlotDataItem(
                self.data_handler.meta_data['stimulus']['time'], self.data_handler.meta_data['stimulus']['values'],
                pen=PlottingStyles.stimulus_pen,
                # name=f'{self.data_handler.data_name}_ROI{self.data_handler.roi_id}',
                name=f'stimulus_trace',
                skipFiniteCheck=True,
                tip=None,
            )
            self.gui.stimulus_plot_item.addItem(plot_data_item)

        # PLOT SINGLE TRACES
        # check if there are single traces plotted
        # item_list = self.gui.stimulus_plot_item.items.copy()
        # for item in item_list:
        #     if item.name().startswith('single_trace'):
        #         self.gui.stimulus_plot_item.removeItem(item)
        #
        # if len(self.data_handler.single_traces) > 0:
        #     cc = 0
        #     for trace in self.data_handler.single_traces:
        #         plot_data_item = pg.PlotDataItem(
        #             trace['time'], trace['values'],
        #             pen=PlottingStyles.single_trace_pen,
        #             name=f'single_trace_{cc}',
        #             skipFiniteCheck=True,
        #             tip=None,
        #         )
        #         self.gui.stimulus_plot_item.addItem(plot_data_item)
        #         cc += 1

    # ==================================================================================================================
    # I/O
    # ------------------------------------------------------------------------------------------------------------------
    def export_flags(self):
        file_dir = self.select_save_file_dir(default_dir=self.settings_file.get('default_dir'),
                                             file_format='csv file, (*.csv)')

        if file_dir:
            # Get Dict
            flags = self.data_handler.meta_data['roi_flags']
            flagged_rois_ls = []
            for roi in flags:
                if not flags[roi]:
                    flagged_rois_ls.append(roi)
            flagged_rois = pd.DataFrame(flagged_rois_ls)
            flagged_rois.columns = ['ROI']
            flagged_rois.to_csv(file_dir)

    def flag_roi(self):
        roi = self.data_handler.roi_id
        flag = np.invert(self.data_handler.meta_data['roi_flags'][roi])
        self.data_handler.meta_data['roi_flags'][roi] = flag
        self.check_flag()

    def check_flag(self):
        flag = self.data_handler.meta_data['roi_flags'][self.data_handler.roi_id]
        if flag:
            self.gui.toolbar_flag_roi.setText('Flag ROI')
        else:
            self.gui.toolbar_flag_roi.setText('Unflag ROI')

    def open_video_converter(self):
        self.video_converter.show()
        print('VIDEO CONVERTER')

    def save_figure(self):
        # Set the desired file format
        file_format = 'JPEG, (*.jpg);; PNG, (*.png);; TIF, (*.tif);; BMP, (*.bmp);; SVG, (*.svg)'
        # file_format = 'PDF, (*.pdf))'

        # Let the User choose a file
        # file_dir = self.select_save_file_dir(default_dir=Settings.default_dir, file_format=file_format)
        file_dir = self.select_save_file_dir(default_dir=self.settings_file.get('default_dir'), file_format=file_format)

        if file_dir:
            file_name = os.path.split(file_dir)[1]
            file_dir = os.path.split(file_dir)[0]
            # create an exporter instance, as an argument give it
            # the item you wish to export
            # exporter = pg.exporters.ImageExporter(plot_item)
            exporter_data_plot = pg.exporters.ImageExporter(self.gui.plot_graphics_layout_widget.scene())
            exporter_stimulus_plot = pg.exporters.ImageExporter(self.gui.stimulus_graphics_layout_widget.scene())

            # set export parameters if needed
            # exporter.parameters()['width'] = 100  # (note this also affects height parameter)

            # save to file
            exporter_data_plot.export(f'{file_dir}/data_{file_name}')
            exporter_stimulus_plot.export(f'{file_dir}/stimulus_{file_name}')

    def import_single_trace(self):
        if self.data_handler.data is not None:
            # Set the desired file format
            file_format = 'csv file, (*.csv)'
            # Let the User choose a file
            file_dir = self.get_a_file_dir(default_dir=self.settings_file.get('default_dir'), file_format=file_format)
            if file_dir:
                stimulus_trace = pd.read_csv(file_dir, index_col=False)
                headers = list(stimulus_trace.keys())
                if 'Time' in headers or 'time' in headers:
                    # There is a time axis
                    data = stimulus_trace.loc[:, stimulus_trace.columns != 'Time'].to_dict(orient='list')
                    # Check if ROIS match ROIS from data traces
                    check = self.data_handler.meta_data['roi_list'] == list(data.keys())
                    if not check:
                        QMessageBox.critical(self.gui, 'ERROR', 'ROIs do not match!')
                        return False
                    # data['Time'] = stimulus_trace['Time'].to_list()
                    t = stimulus_trace['Time'].to_list()
                else:
                    # There is no time axis
                    # Ask for sampling rate
                    # sampling_rate_default = str(0.1)
                    sampling_rate_default = str(self.settings_file.get('stimulus_sampling_dt'))
                    sampling_rate_str, ok_pressed = QInputDialog.getText(
                        self.gui, "Enter dt", "dt [s]:", QLineEdit.EchoMode.Normal, sampling_rate_default)
                    if ok_pressed and sampling_rate_str:
                        try:
                            sampling_rate = 1 / float(sampling_rate_str)
                            sampling_dt = float(sampling_rate_str)
                        except ValueError:
                            QMessageBox.critical(self.gui, 'ERROR', 'Sampling dt Must Be a Number!')
                            return False
                    else:
                        QMessageBox.critical(self.gui, 'ERROR', 'Please Enter Sampling dt')
                        return False

                    # Create time axis with sampling rate
                    try:
                        self.data_handler.meta_data['single_trace_sampling_rate'] = sampling_rate
                        self.data_handler.meta_data['single_trace_dt'] = sampling_dt
                    except IndexError:
                        print('Could not find single trace meta data in data handler')
                    # max_time = stimulus_trace.shape[0] / sampling_rate
                    self.settings_file.modify_setting('stimulus_sampling_dt', sampling_dt)
                    self.settings_file.save_settings()
                    max_time = stimulus_trace.shape[0] * sampling_dt
                    data = stimulus_trace.to_dict(orient='list')
                    # Check if ROIS match ROIS from data traces
                    check = self.data_handler.meta_data['roi_list'] == list(data.keys())
                    if not check:
                        QMessageBox.critical(self.gui, 'ERROR', 'ROIs do not match!')
                        return False

                    # data['Time'] = np.linspace(0, max_time, stimulus_trace.shape[0])
                    t = np.linspace(0, max_time, stimulus_trace.shape[0])

                # Add single traces to data handler
                for trace_key in data:
                    self.data_handler.add_roi_stimulus_trace(roi_id=trace_key, trace_time=t, trace_values=data[trace_key])
                self.plot_single_traces()
        else:
            QMessageBox.critical(self.gui, 'ERROR', 'Please Import Data Traces First!')

    def import_extra_trace(self):
        if self.data_handler.data is not None:
            # Set the desired file format
            file_format = 'csv file, (*.csv)'
            # Let the User choose a file
            file_dir = self.get_a_file_dir(default_dir=self.settings_file.get('default_dir'), file_format=file_format)
            if file_dir:
                roi_list = self.data_handler.meta_data['roi_list']
                extra_trace_df = pd.read_csv(file_dir, index_col=False)
                headers = list(extra_trace_df.keys())
                if 'Time' in headers or 'time' in headers:
                    if 'Time' in headers:
                        time_header = 'Time'
                    else:
                        time_header = 'time'
                    # There is a time axis
                    data = extra_trace_df.loc[:, extra_trace_df.columns != time_header].to_dict(orient='list')
                    # Check if ROIS match ROIS from data traces
                    check = roi_list == list(data.keys())
                    if not check:
                        QMessageBox.critical(self.gui, 'ERROR', 'ROIs do not match!')
                        return False
                    time_axis = extra_trace_df[time_header].to_list()
                    # Compute Sampling Rate
                    t_max = time_axis[-1]
                    sampling_rate = len(time_axis) / t_max
                else:
                    # There is no time axis
                    # Get Sampling Rate from User: Let User choose to give rate or dt
                    sampling_rate_default = str(self.settings_file.get('sampling_rate'))
                    self.get_sampling_rate_window = ImportDataTracesWindow()
                    self.get_sampling_rate_window.set_default_val(default_val=sampling_rate_default)
                    self.get_sampling_rate_window.exec()

                    sampling_rate = self.get_sampling_rate_window.sampling_rate
                    sampling_dt = 1 / self.get_sampling_rate_window.sampling_rate

                    data = extra_trace_df.to_dict(orient='list')
                    # Check if ROIS match ROIS from data traces
                    check = self.data_handler.meta_data['roi_list'] == list(data.keys())
                    if not check:
                        QMessageBox.critical(self.gui, 'ERROR', 'ROIs do not match!')
                        return False

                    # Create time axis with sampling rate
                    max_time = extra_trace_df.shape[0] * sampling_dt
                    time_axis = np.linspace(0, max_time, extra_trace_df.shape[0])

                # Add single traces to data handler
                unique_id = str(time.time_ns())
                for roi in roi_list:
                    self.data_handler.add_extra_trace(name=unique_id, values=data[roi], time=time_axis, roi=roi, fr=sampling_rate)
                self.update_plot(update_axis=False)
        else:
            QMessageBox.critical(self.gui, 'ERROR', 'Please Import Data Traces First!')

    def export_results(self):
        file_dir = self.select_save_file_dir(default_dir=self.settings_file.get('default_dir'), file_format='csv, (*.csv)')
        if self.data_handler.data is not None and file_dir:
            res = self.data_handler.convert_events_to_csv()
            if res:
                result = pd.DataFrame(res)
                result.to_csv(file_dir, index=False)

    def import_meta_data(self):
        if self.data_handler.data is not None:
            # Set the desired file format
            file_format = 'csv file, (*.csv)'
            # Let the User choose a file
            file_dir = self.get_a_file_dir(default_dir=self.settings_file.get('default_dir'), file_format=file_format)
            if file_dir:
                meta_data = pd.read_csv(file_dir, index_col=False).to_dict('records')
                self.data_handler.add_meta_data(meta_data[0])
        else:
            QMessageBox.critical(self.gui, 'ERROR', 'Please Import Data Traces First!')

    def import_stimulus(self):
        if self.data_handler.data is not None:
            # Set the desired file format
            file_format = 'csv file, (*.csv)'
            # Let the User choose a file
            file_dir = self.get_a_file_dir(default_dir=self.settings_file.get('default_dir'), file_format=file_format)
            if file_dir:
                stimulus_times = pd.read_csv(file_dir, index_col=False)
                # dt = 0.001
                dt = self.stimulus_dt
                t_max = self.data_handler.get_time_axis(self.data_handler.roi_id).max()
                time_axis = np.arange(0, t_max, dt)
                stimulus_values = np.zeros_like(time_axis)
                for start, end in zip(stimulus_times['start'].values, stimulus_times['end'].values):
                    idx = (time_axis <= end) * (time_axis >= start)
                    stimulus_values[idx] = 1
                self.data_handler.add_stimulus_trace(stimulus_values, time_axis, stimulus_times)
                self.plot_stimulus()
                self.gui.toolbar_show_stimulus.setDisabled(False)
                self.gui.toolbar_show_stimulus_info.setDisabled(False)
        else:
            QMessageBox.critical(self.gui, 'ERROR', 'Please Import Data Traces First!')

    def import_traces_from_csv2(self):
        # Set the desired file format
        file_format = 'csv file, (*.csv)'
        # Let the User choose a file
        file_dir = self.get_a_file_dir(default_dir=self.settings_file.get('default_dir'), file_format=file_format)
        if file_dir:
            # Get Sampling Rate from User
            # Let User choose to give rate or dt
            sampling_rate_default = str(self.settings_file.get('sampling_dt'))

            sampling_rate_str, ok_pressed = QInputDialog.getText(
                self.gui, "Enter dt", "dt [s]:", QLineEdit.EchoMode.Normal, sampling_rate_default)
            if ok_pressed and sampling_rate_str:
                try:
                    sampling_dt = float(sampling_rate_str)
                    sampling_rate = 1 / sampling_dt
                except ValueError:
                    QMessageBox.critical(self.gui, 'ERROR', 'Sampling Rate Must Be a Number!')
                    return False
            else:
                QMessageBox.critical(self.gui, 'ERROR', 'Please Enter Sampling Rate')
                return False

            self.settings_file.modify_setting('sampling_dt', sampling_dt)
            self.settings_file.save_settings()

            # Open the csv file using pandas
            csv_file = pd.read_csv(file_dir, index_col=False)
            data_name = os.path.split(file_dir)[1][:-4]

            # Start a new session
            self._start_new_session()
            # self.data_handler.sampling_rate = sampling_rate
            # Create a new data set
            roi_list = list(csv_file.keys())
            self.data_handler.create_new_data_set(roi_list=roi_list, data_name=data_name, sampling_rate=sampling_rate)

            # Fill data set with traces in the csv file
            for key in csv_file:
                trace = csv_file[key]
                self.data_handler.add_data_trace(trace.to_numpy(), 'raw', key)

            self.data_handler.change_roi(roi_list[0])
            self.prepare_new_data()

    def import_traces_from_csv(self):
        # Set the desired file format
        file_format = 'csv file, (*.csv)'
        # Let the User choose a file
        file_dir = self.get_a_file_dir(default_dir=self.settings_file.get('default_dir'), file_format=file_format)
        if file_dir:
            # Get Sampling Rate from User
            # Let User choose to give rate or dt
            sampling_rate_default = str(self.settings_file.get('sampling_rate'))
            self.get_sampling_rate_window = ImportDataTracesWindow()
            self.get_sampling_rate_window.set_default_val(default_val=sampling_rate_default)
            self.get_sampling_rate_window.exec()

            sampling_rate = self.get_sampling_rate_window.sampling_rate
            sampling_dt = 1 / self.get_sampling_rate_window.sampling_rate

            self.settings_file.modify_setting('sampling_rate', sampling_rate)
            self.settings_file.modify_setting('sampling_dt', sampling_dt)

            self.settings_file.save_settings()

            # Open the csv file using pandas
            csv_file = pd.read_csv(file_dir, index_col=False)
            data_name = os.path.split(file_dir)[1][:-4]

            # Start a new session
            self._start_new_session()
            # self.data_handler.sampling_rate = sampling_rate
            # Create a new data set
            roi_list = list(csv_file.keys())
            self.data_handler.create_new_data_set(roi_list=roi_list, data_name=data_name, sampling_rate=sampling_rate)

            # Fill data set with traces in the csv file
            for key in csv_file:
                trace = csv_file[key]
                self.data_handler.add_data_trace(trace.to_numpy(), 'raw', key)

            self.data_handler.change_roi(roi_list[0])
            self.prepare_new_data()

    def get_a_file_dir(self, default_dir, file_format):
        if default_dir.exists():
            file_dir = QFileDialog.getOpenFileName(self.gui, 'Open File', default_dir.as_posix(), file_format)[0]
            return file_dir
        else:
            print('Could not find default directory')
            return None

    def select_save_file_dir(self, default_dir, file_format=''):
        if default_dir.exists():
            file_dir = QFileDialog.getSaveFileName(self.gui, 'Save File', default_dir.as_posix(), file_format)[0]
        else:
            print('Could not find default directory')
            return None
        return file_dir

    def _save_file(self):
        file_dir = self.select_save_file_dir(default_dir=self.settings_file.get('default_dir'), file_format='viewer file, (*.vf)')
        if file_dir:
            data = pickle.dumps(self.data_handler.data)
            meta_data = pickle.dumps(self.data_handler.meta_data)
            filter_window = pickle.dumps(self.data_handler.filter_window)

            with ZipFile(file_dir, 'w') as zip_object:
                zip_object.writestr('data.pickle', data)
                zip_object.writestr('meta_data.pickle', meta_data)
                zip_object.writestr('filter_window.pickle', filter_window)

    def _load_file(self):
        file_dir = self.get_a_file_dir(default_dir=self.settings_file.get('default_dir'), file_format='viewer file, (*.vf)')
        if file_dir:
            self._start_new_session()
            with ZipFile(file_dir, 'r') as zip_object:
                data = pickle.loads(zip_object.read('data.pickle'))
                meta_data = pickle.loads(zip_object.read('meta_data.pickle'))
                try:
                    filter_window = pickle.loads(zip_object.read('filter_window.pickle'))
                except KeyError:
                    print('Foun No Filter Settings')
                    filter_window = None

            self.data_handler.load_new_data_set(data=data, meta_data=meta_data)
            self.data_handler.change_roi(self.data_handler.meta_data['roi_list'][0])
            self.prepare_new_data()

            if 'stimulus_trace' in self.data_handler.data[self.data_handler.roi_id]:
                if len(self.data_handler.data[self.data_handler.roi_id]['stimulus_trace']) > 0:
                    self.plot_single_traces()

            if self.data_handler.meta_data['stimulus']['available']:
                self.plot_stimulus()
                self.gui.toolbar_show_stimulus.setDisabled(False)
                self.gui.toolbar_show_stimulus_info.setDisabled(False)
            else:
                self.gui.toolbar_show_stimulus.setDisabled(True)
                self.gui.toolbar_show_stimulus_info.setDisabled(True)

            if filter_window is not None:
                self.data_handler.filter_window = filter_window
                self.gui.filter_slider.setValue(int(self.data_handler.filter_window * 1000))

    # ==================================================================================================================
    # GUI AND DATA HANDLING
    # ------------------------------------------------------------------------------------------------------------------
    def open_video_viewer(self):
        self.video_viewer.show()

    def check_video(self):
        if self.video_connected:
            samples_data = self.data_handler.get_roi_data_trace_size(self.data_handler.roi_id)
            samples_video = self.video_viewer.total_frames
            if samples_video == samples_data:
                self.video_match = True
            else:
                frame_diff = abs(samples_data-samples_video)
                print(f'Video: {samples_video}')
                print(f'Data: {samples_data}')
                print(f'Diff: {frame_diff}')

                self.video_match = False
                self.video_connected = False
                self.video_viewer.connect_to_data_trace()
                QMessageBox.critical(self.gui, 'WARNING', 'Video frame number and data trace sample size DO NOT MATCH! \n'
                                                          'Cannot connect video to data trace')

    def _next_roi(self):
        if self.data_handler.data is not None:
            roi_id_nr = self.data_handler.get_roi_index() + 1
            roi_id_nr = roi_id_nr % self.data_handler.get_roi_count()
            roi_id = self.data_handler.meta_data['roi_list'][roi_id_nr]
            self.data_handler.change_roi(roi_id)
            self.gui.roi_selection_combobox.setCurrentIndex(roi_id_nr)
            # check roi flag status
            self.check_flag()

    def _prev_roi(self):
        if self.data_handler.data is not None:
            roi_id_nr = self.data_handler.get_roi_index() - 1
            roi_id_nr = roi_id_nr % self.data_handler.get_roi_count()
            roi_id = self.data_handler.meta_data['roi_list'][roi_id_nr]
            self.data_handler.change_roi(roi_id)
            # self.data_handler.moving_average_filter()
            self.gui.roi_selection_combobox.setCurrentIndex(roi_id_nr)
            # check roi flag status
            self.check_flag()

    def _set_to_min_max(self):
        self.data_handler.data_norm_mode = 'min_max'
        self.data_handler.moving_average_filter()
        self.update_plot(update_axis=True)
        self.gui.trace_plot_item.setLabel('left', 'Norm. (min/max)', **PlottingStyles.axis_label_styles)

    def _set_to_df(self):
        self.data_handler.data_norm_mode = 'df'
        # self.data_handler.change_roi(new_roi=self.data_handler.roi_id)
        # self.plot_traces(update_axis=True)
        self.data_handler.moving_average_filter()
        self.update_plot(update_axis=True)
        self.gui.trace_plot_item.setLabel('left', 'dF/F', **PlottingStyles.axis_label_styles)

    def _set_to_z_score(self):
        self.data_handler.data_norm_mode = 'z'
        # self.plot_traces(update_axis=True)
        self.data_handler.moving_average_filter()
        self.gui.trace_plot_item.setLabel('left', 'Z-Score (SD)', **PlottingStyles.axis_label_styles)
        self.update_plot(update_axis=True)

    def _set_to_raw(self):
        self.data_handler.data_norm_mode = 'raw'
        # self.plot_traces(update_axis=True)
        self.data_handler.moving_average_filter()
        self.gui.trace_plot_item.setLabel('left', 'Raw', **PlottingStyles.axis_label_styles)
        self.update_plot(update_axis=True)

    def roi_selected(self):
        roi_id = self.gui.roi_selection_combobox.currentData()
        self.data_handler.change_roi(roi_id)

    def get_max_data_values(self):
        # Get min and max values of all rois
        max_vals = []
        min_vals = []
        for roi in self.data_handler.data:
            data = self.data_handler.data[roi]['data_traces'][self.data_handler.data_norm_mode]
            min_vals.append(np.min(data))
            max_vals.append(np.max(data))

        y_min, y_max = np.min(min_vals), np.max(max_vals)

        return y_min, y_max

    @staticmethod
    def random_color():
        start = 50
        end = 200
        r, g, b = np.random.randint(start, end), np.random.randint(start, end), np.random.randint(start, end)
        color = (r, g, b)
        dark_factor = 0.5
        color_darker = (r * dark_factor, g * dark_factor, b * dark_factor)
        return color, color_darker

    def freeze_gui(self, freeze=True, menu=False):
        self.gui.next_button.setDisabled(freeze)
        self.gui.prev_button.setDisabled(freeze)
        self.gui.toolbar_raw_action.setDisabled(freeze)
        self.gui.toolbar_min_max_action.setDisabled(freeze)
        self.gui.toolbar_df_action.setDisabled(freeze)
        self.gui.toolbar_z_score_action.setDisabled(freeze)
        self.gui.toolbar_filter_action.setDisabled(freeze)
        self.gui.toolbar_show_stimulus.setDisabled(freeze)
        self.gui.toolbar_show_stimulus_info.setDisabled(freeze)
        self.gui.roi_selection_combobox.setDisabled(freeze)
        self.gui.filter_slider.setDisabled(freeze)
        self.gui.filter_locK_button.setDisabled(freeze)
        if menu:
            self.gui.file_menu.setDisabled(freeze)
        # self._connect_short_cuts(np.invert(freeze))

    # ==================================================================================================================
    # EVENT MODE HANDLING
    # ------------------------------------------------------------------------------------------------------------------
    def toggle_base_line_trace(self):
        if self.show_fbs:
            self.show_fbs = False
            self.gui.toolbar_fbs_trace_action.setText('Show Baseline')
            self.update_plot()
        else:
            self.show_fbs = True
            self.gui.toolbar_fbs_trace_action.setText('Hide Baseline')
            self.update_plot()

    def set_collection_mode_color(self, on=True):
        if on:
            self.gui.plot_graphics_layout_widget.setBackground(pg.mkColor(PlottingStyles.collecting_mode_bg))
            pen = pg.mkPen(color=(255, 0, 0), width=PlottingStyles.axis_width)
            self.gui.trace_plot_item.getAxis("bottom").setPen(pen)
            self.gui.trace_plot_item.getAxis("bottom").setTextPen(pen)
            self.gui.trace_plot_item.getAxis("bottom").setTickPen(pen)

            self.gui.trace_plot_item.getAxis("left").setPen(pen)
            self.gui.trace_plot_item.getAxis("left").setTextPen(pen)
            self.gui.trace_plot_item.getAxis("left").setTickPen(pen)

            # Freeze GUI
            self.gui.next_button.setDisabled(True)
            self.gui.prev_button.setDisabled(True)
            self.gui.toolbar_raw_action.setDisabled(True)
            self.gui.toolbar_min_max_action.setDisabled(True)
            self.gui.toolbar_df_action.setDisabled(True)
            self.gui.toolbar_z_score_action.setDisabled(True)
            self.gui.toolbar_filter_action.setDisabled(True)
            self.gui.toolbar_show_stimulus.setDisabled(True)
            self.gui.toolbar_show_stimulus_info.setDisabled(True)
            self.gui.roi_selection_combobox.setDisabled(True)
            self.gui.filter_slider.setDisabled(True)
            self.gui.filter_locK_button.setDisabled(True)
            self._connect_short_cuts(False)
        else:
            self.gui.plot_graphics_layout_widget.setBackground('w')
            pen = pg.mkPen(color=(0, 0, 0), width=PlottingStyles.axis_width)
            self.gui.trace_plot_item.getAxis("bottom").setPen(pen)
            self.gui.trace_plot_item.getAxis("bottom").setTextPen(pen)
            self.gui.trace_plot_item.getAxis("bottom").setTickPen(pen)

            self.gui.trace_plot_item.getAxis("left").setPen(pen)
            self.gui.trace_plot_item.getAxis("left").setTextPen(pen)
            self.gui.trace_plot_item.getAxis("left").setTickPen(pen)

            # UnFreeze GUI
            self.gui.next_button.setDisabled(False)
            self.gui.prev_button.setDisabled(False)
            self.gui.toolbar_raw_action.setDisabled(False)
            self.gui.toolbar_min_max_action.setDisabled(False)
            self.gui.toolbar_df_action.setDisabled(False)
            self.gui.toolbar_z_score_action.setDisabled(False)
            self.gui.toolbar_filter_action.setDisabled(False)
            if len(self.data_handler.meta_data['stimulus']) > 0:
                self.gui.toolbar_show_stimulus.setDisabled(False)
                self.gui.toolbar_show_stimulus_info.setDisabled(False)
            self.gui.roi_selection_combobox.setDisabled(False)
            if self.filter_is_active:
                self.gui.filter_slider.setDisabled(False)
                self.gui.filter_locK_button.setDisabled(False)
            self._connect_short_cuts(True)

    def collecting_points(self):
        # Gets triggered when pressing ALT
        if self.point_collection.active:
            self.point_collection.stop_collecting()
            self.set_collection_mode_color(on=False)
        else:
            # Start Point Collection Mode
            self.set_collection_mode_color(on=True)
            if self.filter_is_active:
                trace = self.data_handler.filtered_trace
            else:
                trace = self.data_handler.data[self.data_handler.roi_id]['data_traces'][
                    self.data_handler.data_norm_mode]
            self.point_collection.start_collecting(
                trace_y=trace,
                time_axis=self.data_handler.get_time_axis(self.data_handler.roi_id)
            )

    def processing_taus(self):
        # Collect Points for Analysis
        points = self.point_collection.get_points()
        self.point_collection.stop_collecting()

        if self.tau_collection.active:
            self.tau_collection.stop_collecting()
            self.freeze_gui(freeze=False, menu=True)
        else:
            # Start Collecting Tau Points
            if self.filter_is_active:
                trace = self.data_handler.filtered_trace
            else:
                trace = self.data_handler.data[self.data_handler.roi_id]['data_traces'][
                    self.data_handler.data_norm_mode]

            self.tau_collection.start_collecting(
                trace_y=trace,
                time_axis=self.data_handler.get_time_axis(self.data_handler.roi_id)
            )
            self.tau_collection.start_tau_collecting(points)

    def compute_peak_amplitudes(self, idx_min, idx_max, mode='rise'):
        peak_amplitudes = dict()
        if self.filter_is_active:
            for norm in ['raw', 'min_max', 'df', 'z']:
                filtered_trace = self.data_handler.get_filtered_trace(self.data_handler.roi_id, norm_mode=norm)
                min_y = filtered_trace[idx_min]
                max_y = filtered_trace[idx_max]
                peak_amplitudes[f'peak_filtered_{norm}_{mode}'] = max_y - min_y

        traces = self.data_handler.data[self.data_handler.roi_id]['data_traces']
        for key in traces:
            if key == 'fbs' or 'filtered':
                continue
            trace = traces[key]
            min_y = trace[idx_min]
            max_y = trace[idx_max]
            peak_amplitudes[f'peak_{key}_{mode}'] = max_y - min_y
        return peak_amplitudes

    def collecting_taus(self):
        results = self.tau_collection.get_tau_values()
        self.tau_collection.stop_collecting()

        # Find idx for point 1 and point 3
        p1_t = results['p1_t']
        p2_t = results['p2_t']
        p3_t = results['p3_t']
        time_axis = self.data_handler.get_time_axis(self.data_handler.roi_id)
        idx_1 = np.where(time_axis == p1_t)[0][0]
        idx_2 = np.where(time_axis == p2_t)[0][0]
        idx_3 = np.where(time_axis == p3_t)[0][0]

        # Exponential Fitting
        # # Cut out event
        trace = self.data_handler.data[self.data_handler.roi_id]['data_traces'][self.data_handler.data_norm_mode]
        fit_results = self.data_handler.fitter.fit_event(
            x=time_axis,
            y=trace,
            idx=[idx_1, idx_2, idx_3]
        )
        # Add fitting results
        results.update(fit_results)

        # Compute Peak Amplitudes
        peak_amplitudes_1 = self.compute_peak_amplitudes(idx_min=idx_1, idx_max=idx_2, mode='rise')
        peak_amplitudes_2 = self.compute_peak_amplitudes(idx_min=idx_3, idx_max=idx_2, mode='decay')
        results.update(peak_amplitudes_1)
        results.update(peak_amplitudes_2)

        # Compute random color
        rand_color, rand_color_darker = self.random_color()

        # Add idx and colors
        results.update({
            'start_idx': idx_1,
            'center_idx': idx_2,
            'end_idx': idx_3,
            'pen_color': rand_color,
            'pen_darker_color': rand_color_darker,
            'hover_pen_color': 'r',
            'filter_window': self.data_handler.filter_window,
            'recording_name': self.data_handler.data_name,
            'sampling_rate': self.data_handler.meta_data['sampling_rate'],
            'norm_mode': self.data_handler.data_norm_mode,
        })

        # add event to data handler
        # even_id = self.data_handler.get_events_count(self.data_handler.roi_id)
        # print(f'Event ID: {even_id}')
        self.data_handler.add_event(event_data=results, roi_id=self.data_handler.roi_id)

        self.update_plot(update_axis=False)
        self.set_collection_mode_color(on=False)

    def cut_out_trace(self, start_idx, end_idx, filtered=False):
        time_axis = self.data_handler.get_time_axis(self.data_handler.roi_id)
        if filtered:
            trace = self.data_handler.filtered_trace
        else:
            trace = self.data_handler.data[self.data_handler.roi_id]['data_traces'][self.data_handler.data_norm_mode]
        cut_out = trace[start_idx:end_idx]
        cut_out_time = time_axis[start_idx:end_idx]
        return cut_out_time, cut_out

    def cut_out_trace_for_plotting(self, start_idx, end_idx, roi, filtered=False):
        time_axis = self.data_handler.get_time_axis(roi)
        if filtered:
            trace = self.data_handler.data[roi]['data_traces']['filtered']
        else:
            trace = self.data_handler.data[roi]['data_traces'][self.data_handler.data_norm_mode]
        cut_out = trace[start_idx:end_idx]
        cut_out_time = time_axis[start_idx:end_idx]
        return cut_out_time, cut_out

    def cancel_everything(self):
        if self.point_collection.active:
            self.point_collection.stop_collecting()
            # self.freeze_gui(freeze=False, menu=True)
            self.set_collection_mode_color(on=False)

        if self.tau_collection.active:
            self.tau_collection.stop_collecting()
            self.set_collection_mode_color(on=False)
            # self.freeze_gui(freeze=False, menu=True)

    def remove_event(self, event_id):
        self.hide_event_info_box(event_id, ev=None)
        event_names = [f'{event_id}_trace', f'event_{event_id}', f'Fit_Rise_{event_id}', f'Fit_Decay_{event_id}', f'{event_id}_points']
        for event_name in event_names:
            item_list = self.gui.trace_plot_item.items.copy()
            for item in item_list:
                # if not isinstance(item, pg.TextItem):
                if item.name() == event_name:
                    self.gui.trace_plot_item.removeItem(item)

        self.data_handler.remove_event(self.data_handler.roi_id, event_id)

    def collect_events_for_plotting(self):
        from IPython import embed
        # Get save dir
        save_dir = QFileDialog.getExistingDirectory(self.gui, "Select Directory")
        if save_dir:
            # Loop over all ROIs
            for i, roi in enumerate(self.data_handler.meta_data['roi_list']):
                # Check first if there are any events
                if self.data_handler.data[roi]['events']:
                    fr = self.data_handler.meta_data['sampling_rate']
                    pre_time = 1
                    post_time = 1
                    pre_sp = int(pre_time * fr)
                    post_sp = int(post_time * fr)
                    # Get all events of this ROI
                    events = self.data_handler.data[roi]['events']
                    # Get Stimulus Information
                    s = self.data_handler.meta_data['stimulus']
                    stimulus_trace = s['values']
                    for ev_key in events:
                        # Prepare data frames for csv files
                        result_trace = pd.DataFrame()
                        result_stimulus = pd.DataFrame()
                        result_rise_fit = pd.DataFrame()
                        result_decay_fit = pd.DataFrame()
                        result_goodness_of_fit = pd.DataFrame()

                        event = events[ev_key]
                        start_idx = events[ev_key]['start_idx'] - pre_sp
                        end_idx = events[ev_key]['end_idx'] + post_sp
                        start_time = events[ev_key]['p1_t'] - pre_time
                        end_time = events[ev_key]['p3_t'] + post_time
                        s_start_idx = int(start_time / self.stimulus_dt)
                        s_end_idx = int(end_time / self.stimulus_dt)

                        # Cut out unfiltered trace
                        # trace_t, trace_v = self.cut_out_trace(start_idx=start_idx, end_idx=end_idx, filtered=False)
                        trace_t, trace_v = self.cut_out_trace_for_plotting(start_idx=start_idx, end_idx=end_idx, roi=roi, filtered=False)

                        result_trace['time'] = trace_t
                        result_trace['values'] = trace_v

                        # Cut out filtered trace
                        if self.filter_is_active:
                            # filter_trace_t, filter_trace_v = self.cut_out_trace(start_idx=start_idx, end_idx=end_idx, filtered=True)
                            filter_trace_t, filter_trace_v = self.cut_out_trace_for_plotting(
                                start_idx=start_idx, end_idx=end_idx, roi=roi, filtered=True)
                            result_trace['filtered'] = filter_trace_v

                        # Cut out Stimulus
                        if s['available']:
                            s_t = self.data_handler.meta_data['stimulus']['time']
                            stimulus_cut_out = stimulus_trace[s_start_idx:s_end_idx]
                            stimulus_cut_out_time = s_t[s_start_idx:s_end_idx]
                            result_stimulus['time'] = stimulus_cut_out_time
                            result_stimulus['values'] = stimulus_cut_out

                        # Get Exp. Fits
                        # Cut out the event trace
                        # cut_rise_time, cut_rise_y = self.cut_out_trace(
                        #     start_idx=event['start_idx'], end_idx=event['center_idx'], filtered=self.filter_is_active)
                        # cut_decay_time, cut_decay_y = self.cut_out_trace(
                        #     start_idx=event['center_idx'], end_idx=event['end_idx'], filtered=self.filter_is_active)

                        cut_rise_time, cut_rise_y = self.cut_out_trace_for_plotting(
                            start_idx=event['start_idx'], end_idx=event['center_idx'], roi=roi, filtered=self.filter_is_active)
                        cut_decay_time, cut_decay_y = self.cut_out_trace_for_plotting(
                            start_idx=event['center_idx'], end_idx=event['end_idx'], roi=roi, filtered=self.filter_is_active)

                        # Get the first time point
                        t0_rise = np.min(cut_rise_time)
                        t0_decay = np.min(cut_decay_time)

                        # Normalize x and y values to fit data range
                        rise_exp_t = event['fit_rise_time'] + t0_rise
                        decay_exp_t = event['fit_decay_time'] + t0_decay
                        rise_exp_y = event['fit_rise_y'] * (np.max(cut_rise_y) - np.min(cut_rise_y)) + np.min(cut_rise_y)
                        decay_exp_y = event['fit_decay_y'] * (np.max(cut_decay_y) - np.min(cut_decay_y)) + np.min(cut_decay_y)

                        # Goodness of Fit
                        residuals_rise = cut_rise_y - rise_exp_y
                        residuals_decay = cut_decay_y - decay_exp_y
                        residuals_rise_sd = np.std(residuals_rise)
                        residuals_decay_sd = np.std(residuals_decay)

                        mse_rise = np.sqrt(np.mean(residuals_rise**2))
                        mse_decay = np.sqrt(np.mean(residuals_decay**2))
                        r_squared_rise = self.goodness_of_fit_r_squared(y=cut_rise_y, fit_y=rise_exp_y)
                        r_squared_decay = self.goodness_of_fit_r_squared(y=cut_decay_y, fit_y=decay_exp_y)

                        result_rise_fit['time'] = rise_exp_t
                        result_rise_fit['values'] = rise_exp_y
                        result_rise_fit['residuals'] = residuals_rise
                        result_decay_fit['time'] = decay_exp_t
                        result_decay_fit['values'] = decay_exp_y
                        result_decay_fit['residuals'] = residuals_decay

                        data_norm_mode = self.data_handler.data_norm_mode
                        result_goodness_of_fit['data_norm_mode'] = [data_norm_mode]
                        result_goodness_of_fit['rise_mse'] = [mse_rise]
                        result_goodness_of_fit['rise_r_squared'] = [r_squared_rise]
                        result_goodness_of_fit['rise_residuals_sd'] = [residuals_rise_sd]
                        result_goodness_of_fit['decay_mse'] = [mse_decay]
                        result_goodness_of_fit['decay_r_squared'] = [r_squared_decay]
                        result_goodness_of_fit['decay_residuals_sd'] = [residuals_decay_sd]

                        # Store to HDD
                        result_trace.to_csv(f'{save_dir}/{roi}_{ev_key}_data_trace.csv', index=False)
                        result_trace.to_csv(f'{save_dir}/{roi}_{ev_key}_data_trace.csv', index=False)
                        result_stimulus.to_csv(f'{save_dir}/{roi}_{ev_key}_stimulus.csv', index=False)
                        result_rise_fit.to_csv(f'{save_dir}/{roi}_{ev_key}_rise_fit.csv', index=False)
                        result_decay_fit.to_csv(f'{save_dir}/{roi}_{ev_key}_decay_fit.csv', index=False)
                        result_goodness_of_fit.to_csv(f'{save_dir}/{roi}_{ev_key}_goodness_of_fit.csv', index=False)
                        # Reconstruct Fig for testing
                        # import matplotlib.pyplot as plt
                        # plt.plot(trace_t, trace_v, 'k')
                        # plt.plot(filter_trace_t, filter_trace_v, 'r')
                        # plt.plot(rise_exp_t, rise_exp_y, 'b')
                        # plt.plot(decay_exp_t, decay_exp_y, 'g')
                        # plt.show()
                        # plt.plot(rise_exp_t, residuals_rise, '.b')
                        # plt.plot(decay_exp_t, residuals_decay, '.g')
                        # plt.show()
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)

        msg.setText("Exporting Data Finished!")
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle("Exporting Data")
        # msg.setDetailedText("The details are as follows:")
        # msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        retval = msg.exec()

    @staticmethod
    def goodness_of_fit_r_squared(y, fit_y):
        # residual sum of squares
        ss_res = np.sum((y - fit_y) ** 2)
        # total sum of squares
        ss_tot = np.sum((y - np.mean(fit_y)) ** 2)
        # r-squared
        r2 = 1 - (ss_res / ss_tot)
        return r2

    # ==================================================================================================================
    # DATA TRACE FILTER HANDLING
    # ------------------------------------------------------------------------------------------------------------------
    def lock_filter_slider(self):
        if self.filter_locked:
            # Unlock Filter
            self.gui.filter_slider.setDisabled(False)
            self.gui.filter_locK_button.setText('Unlocked')
            self.filter_locked = False
        else:
            # Lock Filter
            self.gui.filter_slider.setDisabled(True)
            self.gui.filter_locK_button.setText('Locked')
            self.filter_locked = True

    def filter_slider_read(self):
        slider_value = float(self.gui.filter_slider.value())
        slider_value = slider_value / 1000
        return slider_value

    def filter_slider_changed(self):
        self.data_handler.filter_window = self.filter_slider_read()
        self.gui.filter_slider_label.setText(f'Filter Window: {self.data_handler.filter_window} s')

        # Compute Filter
        self.data_handler.moving_average_filter()

        # Plot new trace
        self.update_plot()

    def activate_filter(self):
        if self.filter_is_active:
            # Deactivate Filter
            self.filter_locked = False
            self.filter_is_active = False
            self.lock_filter_slider()
            self.gui.filter_locK_button.setDisabled(True)
            self.data_handler.change_roi(self.data_handler.roi_id)
            # self.plot_filtered_trace()
            self.update_plot()
            self.gui.toolbar_filter_action.setText('Turn Filter ON')
        else:
            # Activate Filter
            self.filter_locked = True
            self.filter_is_active = True
            self.lock_filter_slider()
            self.gui.filter_locK_button.setDisabled(False)
            self.filter_slider_changed()
            self.data_handler.change_roi(self.data_handler.roi_id)
            # self.plot_filtered_trace()
            self.update_plot()
            self.gui.toolbar_filter_action.setText('Turn Filter OFF')

    # ==================================================================================================================
    # MOUSE AND KEY PRESS HANDLING
    # ------------------------------------------------------------------------------------------------------------------
    def on_key_press(self, event):
        if event.key() == Qt.Key.Key_Alt and self.data_handler.data is not None:
            if not self.tau_collection.active:
                self.collecting_points()

        if event.key() == Qt.Key.Key_Return and self.point_collection.is_full:
            # Collect Points for Analysis
            self.processing_taus()

        if event.key() == Qt.Key.Key_Return and self.tau_collection.is_full:
            # Collect Tau Values
            self.collecting_taus()

        if event.key() == Qt.Key.Key_Escape:
            # print('You pressed ESC')
            self.cancel_everything()

    def on_key_release(self, event):
        pass
        # if event.key() == Qt.Key.Key_Control:
        #     self.point_collection.stop_collecting()

    def closeEvent(self, event):
        retval = self.gui.exit_dialog()

        if retval == QMessageBox.StandardButton.Save:
            # Save before exit
            event.accept()
            self._save_file()
        elif retval == QMessageBox.StandardButton.Discard:
            # Do not save before exit
            event.accept()
        else:
            # Do not exit
            event.ignore()

    def exit_app(self):
        self.gui.close()

    def mouse_moved(self, event):
        vb = self.gui.trace_plot_item.vb
        if self.gui.trace_plot_item.sceneBoundingRect().contains(event):
            mouse_point = vb.mapSceneToView(event)
            self.gui.mouse_label.setText(f"<p style='color:black'>X： {mouse_point.x():.4f} <br> Y: {mouse_point.y():.4f}</p>")
