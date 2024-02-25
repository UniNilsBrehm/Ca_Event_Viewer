import numpy as np
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from viewer.settings import PlottingStyles
import pyqtgraph as pg


class PointCollector(QObject):
    signal_full = pyqtSignal()
    signal_not_full = pyqtSignal()
    signal_emtpy = pyqtSignal()
    signal_point_added = pyqtSignal()
    signal_point_removed = pyqtSignal()

    def __init__(self, points_limit):
        QObject.__init__(self)
        self.points = []
        self.points_limit = points_limit
        self.is_full = False

    @staticmethod
    def sort_points(points):
        points = np.array(points)
        idx = np.argsort(points[:, 0])
        points_sorted = points[idx]
        # print(f'Sorted Points: {points_sorted}')
        return points_sorted

    def check_size(self):
        if self.get_count() == self.points_limit:
            self.is_full = True
        else:
            self.is_full = False

    def clear(self):
        self.points = []
        self.signal_not_full.emit()
        self.signal_emtpy.emit()

    def set_points(self, points):
        # sort points
        points = self.sort_points(points)
        self.points = points

    def add_point(self, new_point):
        new_point_number = len(self.points) + 1
        if new_point_number < self.points_limit + 1:
            self.points.append(new_point)
            self.signal_point_added.emit()
        self.check_size()

    def remove_point_by_id(self, point_id):
        if len(self.points) == 0:
            self.signal_emtpy.emit()
            # print('PointCollector is empty!')
        elif point_id < len(self.points):
            del self.points[point_id]
            self.signal_point_removed.emit()
        else:
            pass
            # print('Could not find this point ...')
        self.check_size()

    def remove_point_by_content(self, point):
        point_names = []
        for i, k in enumerate(self.points):
            idx = k == point
            if idx:
                # store point name
                point_names.append(i)
                # print(f'Deleted: Point {i}')

        for k in point_names:
            del self.points[k]
            self.signal_point_removed.emit()
        self.check_size()

    def get_points(self):
        if self.get_count() > 0:
            # sort points by time
            points = self.sort_points(self.points)
            # print(points)
            return points
        else:
            return None

    def get_count(self):
        count = len(self.points)
        # print(count)
        return count


class PointCollectionMode(PointCollector):
    def __init__(self, plot_window, plot_item):
        PointCollector.__init__(self, points_limit=3)
        self.plot_item = plot_item
        self.plot_window = plot_window
        self.active = False
        self.trace_y = None
        self.time_axis = None
        self.plot_style = PlottingStyles.collecting_points

        # self.plot_item.scene().sigMouseMoved.connect(self.mouse_moved)
        # self.plot_item.scene().sigMouseClicked.connect(self.mouse_clicked)

    def start_collecting(self, trace_y, time_axis):
        self.active = True
        self.trace_y = trace_y
        self.time_axis = time_axis
        self.plot_item.scene().sigMouseClicked.connect(self.mouse_clicked)
        self._create_cross_hair()
        self.signal_point_added.connect(self.draw_points)
        self.signal_point_removed.connect(self.draw_points)

    def stop_collecting(self):
        self.active = False
        self.plot_item.scene().sigMouseClicked.disconnect()
        self._remove_cross_hair()
        self.clear()
        self.is_full = False
        self.draw_points()

    def convert_mouse_pos_to_data_pos(self, mouse_x, mouse_y):
        idx1 = self.time_axis >= mouse_x
        t_point1 = self.time_axis[idx1][0]
        time_idx1 = int(np.where(self.time_axis == t_point1)[0][0])

        idx2 = self.time_axis < mouse_x
        t_point2 = self.time_axis[idx2][-1]
        time_idx2 = int(np.where(self.time_axis == t_point2)[0][0])

        time_diff1 = abs(mouse_x - t_point1)
        time_diff2 = abs(mouse_x - t_point2)

        if time_diff1 <= time_diff2:
            time_value = t_point1
            time_idx = time_idx1
        else:
            time_value = t_point2
            time_idx = time_idx2

        data_y = self.trace_y[time_idx]
        data_x = time_value

        return data_x, data_y

    def point_clicked(self, _, points, event):
        # Remove shift+clicked Item from Point Collector and Plot
        if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            item_name = points[0].index()
            self.remove_point_by_id(item_name)

    def draw_points(self):
        # check if there is already a plotted trace
        item_list = self.plot_item.items
        for item in item_list:
            # if not isinstance(item, pg.TextItem):
            if item.name() == 'Points_Plot':
                self.plot_item.removeItem(item)

        points = self.get_points()
        if points is not None:
            x = points[:, 0]
            y = points[:, 1]

            scatter_plot_item = pg.ScatterPlotItem(
                x=x, y=y,
                hoverable=True,
                name='Points_Plot',
                tip=None,
                **self.plot_style
            )
            scatter_plot_item.sigClicked.connect(self.point_clicked)
            self.plot_item.addItem(scatter_plot_item)

    def mouse_clicked(self, event):
        self.plot_item.scene().setClickRadius(20)
        vb = self.plot_item.vb
        scene_coords = event.scenePos()
        key_modifier = event.modifiers()
        # if the click is inside the bounding box of the plot
        if self.plot_item.sceneBoundingRect().contains(scene_coords) and key_modifier != Qt.KeyboardModifier.ShiftModifier:
            # Normal Point Add Mode
            mouse_point = vb.mapSceneToView(scene_coords)
            mx = mouse_point.x()
            my = mouse_point.y()
            data_x, data_y = self.convert_mouse_pos_to_data_pos(mx, my)
            self.add_point([data_x, data_y])

        # if key_modifier == Qt.KeyboardModifier.AltModifier and len(self.points) == self.points_limit:
        #     print('COLLECTING POINTS')

    def _create_cross_hair(self):
        # Create CrossHair
        # https://www.pythonguis.com/faq/pyqt-show-custom-cursor-pyqtgraph/
        # self.new_cursor = Qt.CursorShape.CrossCursor
        self.new_cursor = Qt.CursorShape.BlankCursor
        self.plot_window.setCursor(self.new_cursor)

        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='k', width=2))
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(color='k', width=2))
        self.plot_item.addItem(self.crosshair_v, ignoreBounds=True)
        self.plot_item.addItem(self.crosshair_h, ignoreBounds=True)
        self.proxy = pg.SignalProxy(self.plot_item.scene().sigMouseMoved, rateLimit=300, slot=self.update_crosshair)

    def _remove_cross_hair(self):
        self.new_cursor = Qt.CursorShape.ArrowCursor
        self.plot_window.setCursor(self.new_cursor)
        self.plot_item.removeItem(self.crosshair_v)
        self.plot_item.removeItem(self.crosshair_h)

    def update_crosshair(self, e):
        pos = e[0]
        vb = self.plot_item.vb
        if self.plot_item.sceneBoundingRect().contains(pos):
            mousePoint = vb.mapSceneToView(pos)
            self.crosshair_v.setPos(mousePoint.x())
            self.crosshair_h.setPos(mousePoint.y())


class TauCollectionMode(PointCollectionMode):
    def __init__(self, plot_window, plot_item):
        PointCollectionMode.__init__(self, plot_window, plot_item)
        self.points_limit = 2
        self.label_points = None
        self.tau_rise_line = None
        self.tau_decay_line = None
        self.plot_style = PlottingStyles.tau_points_symbols

    def convert_mouse_pos_to_data_pos(self, mouse_x, mouse_y):
        return mouse_x, mouse_y

    def start_tau_collecting(self, label_points):
        self.add_label_points(label_points)
        self.compute_tau_lines()

    def stop_collecting(self):
        self.active = False
        self.plot_item.scene().sigMouseClicked.disconnect()
        self._remove_cross_hair()
        self.clear()
        self.is_full = False
        self.remove_tau_lines()
        self.draw_points()

    def remove_tau_lines(self):
        if self.tau_rise_line_plot is not None:
            self.plot_item.removeItem(self.tau_rise_line_plot)
        if self.tau_decay_line_plot is not None:
            self.plot_item.removeItem(self.tau_decay_line_plot)

    def _draw_tau_lines(self):
        self.tau_rise_line_plot = pg.PlotDataItem(
            self.tau_rise_line[0], self.tau_rise_line[1],
            pen=pg.mkPen(color='r', width=3),
            name='tau_rise_line',
            tip=None,
        )
        self.plot_item.addItem(self.tau_rise_line_plot)

        self.tau_decay_line_plot = pg.PlotDataItem(
            self.tau_decay_line[0], self.tau_decay_line[1],
            pen=pg.mkPen(color='b', width=3),
            name='tau_decay_line',
            tip=None,
        )
        self.plot_item.addItem(self.tau_decay_line_plot)

    def add_label_points(self, label_points):
        self.label_points = label_points

    def compute_tau_lines(self):
        # 1. Sort the points by time
        points = self.sort_points(self.label_points)
        p1 = points[0]
        p2 = points[1]
        p3 = points[2]

        # 2. Compute y value for tau rise
        y_diff = abs(p2[1] - p1[1])
        tau_rise_y = (1 - 1 / np.exp(1)) * y_diff + p1[1]
        self.tau_rise_line = ([p1[0], p2[0]], [tau_rise_y, tau_rise_y])

        # 3. Compute y value for tau decay
        y_diff = abs(p3[1] - p2[1])
        tau_decay_y = (1 / np.exp(1)) * y_diff + p3[1]
        self.tau_decay_line = ([p2[0], p3[0]], [tau_decay_y, tau_decay_y])

        self._draw_tau_lines()

    def get_tau_values(self):
        if len(self.points) == 2:
            points = self.sort_points(self.points)
            tau_rise_t0 = self.label_points[0][0]
            tau_decay_t0 = self.label_points[1][0]

            tau_rise_y = points[1][1]
            tau_decay_y = points[0][1]
            tau_rise_time_point = points[0][0]
            tau_decay_time_point = points[1][0]
            tau_rise = tau_rise_time_point - tau_rise_t0
            tau_decay = tau_decay_time_point - tau_decay_t0
            result = {
                'tau_rise': tau_rise,
                'tau_decay': tau_decay,
                'p1_t': self.label_points[0][0],
                'p2_t': self.label_points[1][0],
                'p3_t': self.label_points[2][0],
                'p1_y': self.label_points[0][1],
                'p2_y': self.label_points[1][1],
                'p3_y': self.label_points[2][1],
            }

            return result
        else:
            # print('ERROR NOT ENOUGH POINTS')
            return None
