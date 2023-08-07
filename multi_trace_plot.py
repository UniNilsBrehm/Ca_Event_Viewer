import sys
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QLabel, QProgressBar
import pyqtgraph as pg
import numpy as np
from time import perf_counter


class MultiPlotScrollArea(QMainWindow):

    row_finished = pyqtSignal(int)

    def __init__(self, data, plot_height=200):
        super().__init__()
        self.num_plots = data.shape[0]
        self.num_points = data.shape[1]
        self.plot_height = plot_height

        # Generate some sample data
        # self.data = [np.random.rand(self.num_points) for _ in range(self.num_plots)]
        self.data = data

        # Set up the main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)

        # Create a scroll area and plot area widget
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)  # Allow the widget to resize
        layout.addWidget(self.scroll_area)

        # Create a widget to contain the vertically arranged plot widgets
        self.plot_widget_container = QWidget()
        self.scroll_area.setWidget(self.plot_widget_container)

        # Set up the layout for the vertically arranged plot widgets
        # The Plots
        self.plot_layout = QVBoxLayout()
        self.plot_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Create a plot widget for each trace and add them to the vertical layout
        # This can take (block) some seconds

        # self.progress_win = QWidget()
        # self.progress = QProgressBar(self.progress_win)
        # self.progress_win.show()
        # self.progress.setMaximum(self.num_plots)
        # self.progress.setGeometry(200, 80, 250, 20)

        # self.plot_widgets = [pg.PlotWidget() for _ in range(self.num_plots)]

        # self.plot_widgets = []
        # for k in range(self.num_plots):
        #     self.plot_widgets.append(pg.PlotWidget())
        #
        # for i, plot in enumerate(self.plot_widgets):
        #     # Set a fixed height for each plot
        #     plot.setMinimumHeight(self.plot_height)
        #     plot_label = QLabel(f'ROI {i}')
        #     row_layout = QHBoxLayout()
        #     row_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        #     row_layout.addWidget(plot_label)
        #     row_layout.addWidget(plot)
        #     plot_layout.addLayout(row_layout)

            # Set the x-axis range to the initial range with auto pan disabled
            # plot.setXRange(0, self.num_points, padding=0)
            # plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
            # plot.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.plot_widget_container.setLayout(self.plot_layout)

        # Connect the scroll bar's valueChanged signal to the update_plots function
        # self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_plots)

        # Set the initial position of the scroll bar to 0 (topmost position)
        self.scroll_area.verticalScrollBar().setValue(0)
        self.plot_widgets = []

        # self.scroll_area.horizontalScrollBar().setValue(0)

        # Update the plots initially
        # self.plot_data()

    def start(self):
        self.plot_widgets = []
        for k in range(self.num_plots):
            self.plot_widgets.append(pg.PlotWidget())
            self.row_finished.emit(k)

        for i, plot in enumerate(self.plot_widgets):
            # Set a fixed height for each plot
            plot.setMinimumHeight(self.plot_height)
            plot_label = QLabel(f'ROI {i}')
            row_layout = QHBoxLayout()
            row_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(plot_label)
            row_layout.addWidget(plot)
            self.plot_layout.addLayout(row_layout)

        self.plot_data()

    def plot_data(self):
        # Loop over all traces and plot each of them into a separate plot item
        for i, plot_widget in enumerate(self.plot_widgets):
            y_data = self.data[i]
            plot_widget.plot(y_data, pen=pg.mkPen(color='k'), clear=True)

    def resizeEvent(self, event):
        # Ensure the scroll bar remains at the top when resizing the window
        self.scroll_area.verticalScrollBar().setValue(0)
        # self.scroll_area.horizontalScrollBar().setValue(0)
        super().resizeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    num_plots = 10
    num_points = 1000
    data_set = np.array([np.random.rand(num_points) for _ in range(num_plots)])
    window = MultiPlotScrollArea(data_set, plot_height=100)
    window.show()
    sys.exit(app.exec())
