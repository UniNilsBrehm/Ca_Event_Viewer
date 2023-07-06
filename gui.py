from PyQt6.QtGui import QFont, QAction, QContextMenuEvent
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtWidgets import QMainWindow, QPushButton, QWidget, QLabel, QVBoxLayout, \
    QMessageBox, QHBoxLayout, QSlider, QComboBox, QToolBar
import pyqtgraph as pg


class MyToolbar(QToolBar):
    def __init__(self):
        QToolBar.__init__(self)

    def contextMenuEvent(self, a0: QContextMenuEvent) -> None:
        # Turn off right click context menu
        pass


class MainWindow(QMainWindow):
    # PyQT Signals
    key_modifier_pressed = pyqtSignal(int)
    key_pressed = pyqtSignal(QEvent)
    key_released = pyqtSignal(QEvent)

    def __init__(self, screen):
        super().__init__()
        self.screen = screen

        # Filter Settings
        # Values in ms
        self.filter_min = 0
        self.filter_max = 10 * 1000
        self.filter_interval = 10
        self.filter_default = 5 * 1000
        self.filter_on = False

        # Setup GUI Elements
        self._setup_ui()

        # Set Window Size
        # self.resize(800, 800)
        screen_h = self.screen.height()
        screen_w = self.screen.width()
        # self.showMaximized()
        # setGeometry(left, top, width, height)
        window_width = 1000
        window_height = 800
        self.setGeometry(screen_w // 2 - window_width // 2, screen_h // 2 - window_height // 2, window_width,
                         window_height)

    def _setup_ui(self):
        self.setWindowTitle("Ca Event Analysis")
        # Central Widget of the Main Window
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Create Widgets
        self._setup_plot()

        # The Toolbar
        # self.toolbar = QToolBar()
        self.toolbar = MyToolbar()
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)
        self.toolbar.toggleViewAction().setEnabled(False)
        self.addToolBar(self.toolbar)

        # Raw F Button
        self.toolbar_raw_action = QAction("raw F", self)
        # self.toolbar_raw_action.setStatusTip("Raw Data (R)")
        self.toolbar_raw_action.setToolTip("Raw Data (R)")
        self.toolbar.addAction(self.toolbar_raw_action)
        # self.shortcut_toolbar_raw_action = QShortcut(QKeySequence('R'), self)

        # Normalized Raw F Button
        self.toolbar_min_max_action = QAction("Norm F", self)
        self.toolbar_min_max_action.setToolTip("Norm Raw Data (F1)")
        self.toolbar.addAction(self.toolbar_min_max_action)
        # self.shortcut_toolbar_raw_norm_action = QShortcut(QKeySequence('N'), self)

        # dF/F Button
        self.toolbar_df_action = QAction("dF/F", self)
        self.toolbar_df_action.setToolTip("dF/F (F)")
        self.toolbar.addAction(self.toolbar_df_action)
        # self.shortcut_toolbar_df_action = QShortcut(QKeySequence('F'), self)

        # Z Score Button
        self.toolbar_z_score_action = QAction("Z-Score", self)
        self.toolbar_z_score_action.setToolTip("Z-Scores (Z)")
        self.toolbar.addAction(self.toolbar_z_score_action)
        # self.shortcut_toolbar_z_score_action = QShortcut(QKeySequence('Z'), self)

        self.toolbar.addSeparator()
        # Show Baseline
        self.toolbar_fbs_trace_action = QAction("Show Baseline", self)
        self.toolbar_fbs_trace_action.setToolTip("Show Baseline")
        self.toolbar.addAction(self.toolbar_fbs_trace_action)
        self.toolbar.addSeparator()

        # Filter Button
        self.toolbar_filter_action = QAction("Turn Filter ON", self)
        self.toolbar_filter_action.setToolTip("Moving Average Filter (L)")
        self.toolbar.addAction(self.toolbar_filter_action)
        self.toolbar_filter_action.setDisabled(True)
        # self.shortcut_toolbar_filter_action = QShortcut(QKeySequence('L'), self)

        self.toolbar.addSeparator()

        # Show Stimulus Button
        self.toolbar_show_stimulus = QAction("Show Stimulus", self)
        self.toolbar_show_stimulus.setToolTip("Toggle Stimulus (H)")
        self.toolbar.addAction(self.toolbar_show_stimulus)
        self.toolbar_show_stimulus.setDisabled(True)
        # self.shortcut_toolbar_show_stimulus = QShortcut(QKeySequence('H'), self)

        # Show Event Info Box Button
        # self.toolbar_show_event_info = QAction("Hide Info Box", self)
        # self.toolbar_show_event_info.setToolTip("Toggle Info Box (E)")
        # self.toolbar.addAction(self.toolbar_show_event_info)
        # self.toolbar_show_event_info.setDisabled(True)
        # self.shortcut_toolbar_show_event_info = QShortcut(QKeySequence('E'), self)

        # Show Stimulus Info Box Button
        self.toolbar_show_stimulus_info = QAction("Show Stimulus Info Box", self)
        self.toolbar_show_stimulus_info.setToolTip("Toggle Info Box (J)")
        self.toolbar.addAction(self.toolbar_show_stimulus_info)
        self.toolbar_show_stimulus_info.setDisabled(True)
        # self.shortcut_toolbar_show_stimulus_info = QShortcut(QKeySequence('J'), self)

        # The Mouse Position
        self.layout_labels = QHBoxLayout()
        self.mouse_label = QLabel(f"<p style='color:black'>X： {0} <br> Y: {0}</p>")

        # Info Label
        self.info_label = QLabel('Please Open Data File ...')
        self.info_frame_rate = QLabel('')

        # ROI Selection Drop Down
        self.roi_selection_combobox_label = QLabel('ROI: ')
        self.roi_selection_combobox = QComboBox()

        # Filter Slider
        self.filter_slider = QSlider(Qt.Orientation.Horizontal)
        self.filter_slider.setMinimum(self.filter_min)
        self.filter_slider.setMaximum(self.filter_max)
        self.filter_slider.setValue(self.filter_default)
        self.filter_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.filter_slider.setTickInterval(self.filter_interval)
        self.filter_slider_label = QLabel(f'Filter Window {int(self.filter_default / 1000)} s')
        self.filter_locK_button = QPushButton('Locked')
        self.filter_slider.setDisabled(True)
        self.filter_locK_button.setDisabled(True)

        # Create Layout
        self.layout_labels.addWidget(self.mouse_label)
        self.layout_labels.addStretch()
        self.layout_labels.addWidget(self.info_label)
        self.layout_labels.addStretch()
        self.layout_labels.addWidget(self.info_frame_rate)
        self.layout_labels.addStretch()
        self.layout_labels.addWidget(self.roi_selection_combobox_label)
        self.layout_labels.addWidget(self.roi_selection_combobox)
        self.layout_labels.addStretch()
        self.layout_labels.addWidget(self.filter_locK_button)
        self.layout_labels.addWidget(self.filter_slider_label)
        self.layout_labels.addWidget(self.filter_slider)

        # buttons
        button_text_font = QFont('Sans Serif', 12)
        button_text_font.setBold(True)
        self.next_button = QPushButton('>>', self)
        self.prev_button = QPushButton('<<', self)
        self.next_button.setFont(button_text_font)
        self.prev_button.setFont(button_text_font)

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Set Button Layout
        layout_buttons = QHBoxLayout()
        layout_buttons.addWidget(self.prev_button)
        layout_buttons.addWidget(self.next_button)

        # Set Main Layout
        # Vertical Box Layout
        layout = QVBoxLayout()

        # Add the widgets to the layout
        layout.addLayout(self.layout_labels)
        layout.addWidget(self.stimulus_graphics_layout_widget)
        layout.addWidget(self.plot_graphics_layout_widget)
        layout.addLayout(layout_buttons)
        layout.setStretchFactor(self.stimulus_graphics_layout_widget, 1)
        layout.setStretchFactor(self.plot_graphics_layout_widget, 4)
        # Connect the layout to the central widget
        self.centralWidget.setLayout(layout)

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # File Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("&File")
        self.file_menu_action_new_session = self.file_menu.addAction('New ... (ctrl+n)')
        self.file_menu_action_open_viewer_file = self.file_menu.addAction('Open Viewer File (ctrl+o)')
        self.file_menu_action_save_viewer_file = self.file_menu.addAction('Save Viewer File (ctrl+s)')
        self.file_menu_action_save_viewer_file.setDisabled(True)

        self.file_menu.addSeparator()
        self.file_menu_action_import_traces = self.file_menu.addAction('Import Data Traces (ctrl+i)')
        self.file_menu_action_import_stimulus = self.file_menu.addAction('Import Stimulus (ctrl+b)')
        self.file_menu_action_import_stimulus_trace = self.file_menu.addAction('Import Stimulus Trace')
        self.file_menu_action_import_meta_data = self.file_menu.addAction('Import Meta Data (ctrl+m)')
        self.file_menu.addSeparator()
        self.file_menu_action_save_csv = self.file_menu.addAction('Export Results to .csv (ctrl+e)')
        self.file_menu_action_save_csv.setDisabled(True)
        self.file_menu.addSeparator()
        self.file_menu_action_noise = self.file_menu.addAction('Compute Noise Statistics')
        self.file_menu.addSeparator()

        self.file_menu_action_exit = self.file_menu.addAction('Exit')

    def _setup_plot(self):
        # pyqtgraph graphic widget (for plotting later)
        self.plot_graphics_layout_widget = pg.GraphicsLayoutWidget(show=True, title="Ca Imaging")
        self.stimulus_graphics_layout_widget = pg.GraphicsLayoutWidget(show=True, title="Ca Imaging")

        # pyqtgraph settings
        # self.plot_graphics_layout_widget.setWindowTitle('Ca Trace')

        # Add a plot item to initialize plot window
        # Stimulus Plot
        self.stimulus_plot_item = self.stimulus_graphics_layout_widget.addPlot(title='Stimulus', clear=True, name='stimulus')
        self.stimulus_plot_item.setMenuEnabled(False)
        self.stimulus_plot_item.hideButtons()
        # Data Plot
        self.trace_plot_item = self.plot_graphics_layout_widget.addPlot(title='Ca Data', clear=True, name='data')
        self.trace_plot_item.setMenuEnabled(False)
        self.trace_plot_item.hideButtons()
        self.stimulus_plot_item.setXLink(self.trace_plot_item)


    def keyPressEvent(self, event):
        super(MainWindow, self).keyPressEvent(event)
        self.key_pressed.emit(event)

    def keyReleaseEvent(self, event):
        super(MainWindow, self).keyReleaseEvent(event)
        self.key_released.emit(event)

    # def closeEvent(self, event):
    #     retval = self.exit_dialog()
    #
    #     if retval == QMessageBox.StandardButton.Save:
    #         # Save before exit
    #         event.accept()
    #     elif retval == QMessageBox.StandardButton.Discard:
    #         # Do not save before exit
    #         event.accept()
    #     else:
    #         # Do not exit
    #         event.ignore()

    def exit_app(self):
        self.close()

    @staticmethod
    def exit_dialog():
        msg_box = QMessageBox()
        msg_box.setText('Exit ...')
        msg_box.setInformativeText('Do you want to save your changes?')
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
        retval = msg_box.exec()
        return retval
