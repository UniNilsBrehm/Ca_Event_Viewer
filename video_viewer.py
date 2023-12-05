import os
import cv2
import tifffile
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QFileDialog
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from pyqtgraph import ImageView
import subprocess as sp
import numpy as np
# from IPython import embed

FFMPEG_BIN = 'C:/FFmpegTool/bin/ffmpeg.exe'


class VideoViewer(QMainWindow):

    FrameChanged = pyqtSignal()
    VideoLoaded = pyqtSignal()
    ConnectToDataTrace = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Create the main widget and layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Create the video frame viewer
        self.video_label = QLabel(f'Please Open A Video File')
        # self.speed_label = QLabel('')
        self.image_view = ImageView(self)

        # Connect Mouse Click
        self.image_view.scene.sigMouseClicked.connect(self.mouse_clicked)

        # self.hist = self.image_view.getHistogramWidget()
        # self.hist.sigLevelsChanged.connect(self.hist_lvl_changed)
        # self.hist_lvl = self.hist.getLevels()

        self.layout.addWidget(self.video_label)
        # self.layout.addWidget(self.speed_label)
        self.layout.addWidget(self.image_view)

        # Create the control widgets
        self.controls_layout = QVBoxLayout()
        self.control_button_layout = QHBoxLayout()

        # Buttons
        self.open_button = QPushButton("Open Video", self)
        self.open_button.clicked.connect(self.open_file_dialog)
        self.control_button_layout.addWidget(self.open_button)

        self.play_button = QPushButton("Play", self)
        self.play_button.clicked.connect(self.play_video)
        self.control_button_layout.addWidget(self.play_button)

        self.pause_button = QPushButton("Pause", self)
        self.pause_button.clicked.connect(self.pause_video)
        self.control_button_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Stop", self)
        self.stop_button.clicked.connect(self.stop_video)
        self.control_button_layout.addWidget(self.stop_button)

        self.faster_button = QPushButton("Faster", self)
        self.faster_button.clicked.connect(self.speed_up)
        self.control_button_layout.addWidget(self.faster_button)

        self.slower_button = QPushButton("Slower", self)
        self.slower_button.clicked.connect(self.slow_down)
        self.control_button_layout.addWidget(self.slower_button)

        self.rotate_button = QPushButton("Rotate", self)
        self.rotate_button.clicked.connect(self.rotate_video)
        self.control_button_layout.addWidget(self.rotate_button)

        self.connect_video_to_data_trace_button = QPushButton("Connect to Data", self)
        self.connect_video_to_data_trace_button.clicked.connect(self.connect_to_data_trace)
        self.control_button_layout.addWidget(self.connect_video_to_data_trace_button)

        # Slider
        self.frame_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.frame_slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.frame_slider.setTickInterval(1)
        self.frame_slider.valueChanged.connect(self.change_frame)
        self.control_button_layout.addWidget(self.frame_slider)

        self.current_frame_label = QLabel("Current Frame: 0", self)
        self.control_button_layout.addWidget(self.current_frame_label)

        self.controls_layout.addWidget(self.frame_slider)
        self.controls_layout.addLayout(self.control_button_layout)
        self.layout.addLayout(self.controls_layout)

        # Disabled Buttons for start up
        self.set_button_state(True)
        self.roi_circle = None

        # Initialize video variables
        self._reset_video_viewer()

        self.pipe = None

    def mouse_clicked(self, event):
        self.image_view.scene.setClickRadius(20)
        vb = self.image_view.getView()
        scene_coords = event.scenePos()
        key_modifier = event.modifiers()
        # if the click is inside the bounding box of the plot
        if vb.boundingRect().contains(scene_coords):
            mouse_point = vb.mapSceneToView(scene_coords)
            mx = mouse_point.x()
            my = mouse_point.y()
            print(mx, my)
            self.roi_circle = (int(mx), int(my))
            self.update_frame()
            # self.roi_circle = cv2.circle(self.video_frame, (mx, my), radius=10, color='r', thickness=2)

    def open_file_dialog(self):
        input_file, _ = QFileDialog.getOpenFileName(
            self, "Select Input File", "", "Video Files (*.mp4; *.avi; *.mkv; *.mpg; *.mpeg; *.tif; *.tiff *.TIF; *.TIFF)")
        if input_file:
            self.load_video(input_file)

    def ffmpeg_read_frame(self):
        # 400 * 288 * 3 bytes (= 1 frame)
        raw_image = self.pipe.stdout.read(420*288*3)

        # transform the byte read into a numpy array
        image = np.fromstring(raw_image, dtype='uint8')
        self.video_frame = image.reshape((288, 420, 3))

        # throw away the data in the pipe's buffer.
        self.pipe.stdout.flush()

    def load_video(self, video_file):
        if self.captured_video is not None:
            self.close_file()
            self._reset_video_viewer()

        self.video_file = video_file
        self.current_frame = 0
        self.total_frames = 0
        if self.video_file.endswith(('.tif', '.tiff', '.TIF', '.TIFF')):
            # This is a tiff file
            # Open the TIFF file in a memory-mapped mode
            self.captured_video = tifffile.TiffFile(video_file, mode='r')
            # Get the number of pages (image stack size)
            self.total_frames = len(self.captured_video.pages)
            self.is_tiff = True
            self.fps = 30
            # Read one frame
            self.video_frame = self.captured_video.pages.get(0).asarray()
        else:
            # Read one frame
            # FFMPEG Method:
            # Open File and direct it to python
            # command = [FFMPEG_BIN,
            #            '-i', self.video_file,
            #            '-f', 'image2pipe',
            #            '-pix_fmt', 'rgb24',
            #            '-vcodec', 'rawvideo', '-']
            # self.pipe = sp.Popen(command, stdout=sp.PIPE, bufsize=10 ** 8)
            #
            # # read the first frame
            # self.ffmpeg_read_frame()

            # OpenCV Method:
            self.captured_video = cv2.VideoCapture(self.video_file)
            self.fps = self.captured_video.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.captured_video.get(cv2.CAP_PROP_FRAME_COUNT))

            self.captured_video.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame - 1)
            ret, self.video_frame = self.captured_video.read()
            self.is_tiff = False

        self.frame_slider.setRange(0, self.total_frames - 1)
        self.current_frame_label.setText(f"Current Frame: {self.current_frame}")
        self.image_view.setImage(self.rotate_frame(self.video_frame), autoLevels=True)
        self.frame_slider.setValue(0)
        # self.video_label.setText(f'Video File: {os.path.split(video_file)[1]}, {self.fps:.2f} Hz')

        # Activate Buttons (False: Show Buttons)
        self.set_button_state(False)
        self.VideoLoaded.emit()

    def set_button_state(self, state):
        self.frame_slider.setDisabled(state)
        self.play_button.setDisabled(state)
        self.pause_button.setDisabled(state)
        self.stop_button.setDisabled(state)
        self.rotate_button.setDisabled(state)
        self.faster_button.setDisabled(state)
        self.slower_button.setDisabled(state)
        self.connect_video_to_data_trace_button.setDisabled(state)

    def play_video(self):
        if self.video_frame is None:
            return
        # self.timer.start(33)  # 30 frames per second (33 milliseconds per frame)
        # ms = self.ms_per_frame[self.ms_per_frame_id]
        # ms = int((1/self.fps) * 1000)
        ms = 33

        self.timer.start(ms)  # 30 frames per second (33 milliseconds per frame)
        # self.speed_label.setText(f'speed: {self.ms_per_frame_base / ms} x')

    def pause_video(self):
        self.timer.stop()

    def stop_video(self):
        self.timer.stop()
        self.current_frame = 0
        if self.captured_video is not None:
            if self.is_tiff:
                self.video_frame = self.captured_video.pages.get(self.current_frame).asarray()
            else:
                self.captured_video.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame - 1)
                ret, self.video_frame = self.captured_video.read()

            self.image_view.setImage(self.rotate_frame(self.video_frame), autoLevels=True)
            self.current_frame_label.setText(f"Current Frame: {self.current_frame}")
            self.frame_slider.setValue(0)

    def speed_up(self):
        if self.ms_per_frame_id > 1:
            # self.speed_id = (self.speed_id - 1) % len(self.speed_factors)
            self.ms_per_frame_id -= 1
            self.timer.stop()
            self.play_video()

    def slow_down(self):
        if self.ms_per_frame_id < len(self.ms_per_frame) - 1:
            # self.speed_id = (self.speed_id + 1) % len(self.speed_factors)
            self.ms_per_frame_id += 1
            self.timer.stop()
            self.play_video()

    def update_frame(self):
        if self.captured_video is not None:
            self.current_frame += 1
            if self.current_frame >= self.total_frames:
                self.current_frame = 0
            self.change_frame(self.current_frame)
            self.FrameChanged.emit()
            self.frame_slider.setValue(self.current_frame)

    def change_frame(self, frame):
        if self.captured_video is not None:
            self.current_frame = frame
            if self.current_frame >= self.total_frames:
                self.current_frame = 0

            self.FrameChanged.emit()
            if self.is_tiff:
                self.video_frame = self.captured_video.pages.get(self.current_frame).asarray()
                if self.roi_circle is not None:
                    # v_frame = np.uint8(self.video_frame)
                    # v_frame = cv2.cvtColor(v_frame, cv2.COLOR_GRAY2RGB)
                    # self.video_frame = cv2.cvtColor(self.video_frame, cv2.COLOR_GRAY2RGB)
                    # self.video_frame = cv2.circle(v_frame, self.roi_circle, radius=60, color=(255, 0, 0), thickness=2)
                    self.video_frame = cv2.circle(self.video_frame, self.roi_circle, radius=60, color=(255, 0, 0), thickness=2)
            else:
                # self.ffmpeg_read_frame()
                # Capture the next frame
                self.captured_video.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame - 1)
                ret, self.video_frame = self.captured_video.read()
                if not ret:
                    return
                if self.roi_circle is not None:
                    self.video_frame = cv2.circle(self.video_frame, self.roi_circle, radius=60, color=(255, 0, 0), thickness=2)

            self.current_frame_label.setText(f"Current Frame: {self.current_frame}")
            self.image_view.setImage(self.rotate_frame(self.video_frame), autoLevels=False)
            # self.image_view.setImage(self.rotate_frame(self.video_frame), autoLevels=True)

    def connect_to_data_trace(self):
        if not self.connected_to_data_trace:
            self.connected_to_data_trace = True
            self.connect_video_to_data_trace_button.setText("Disconnect")
        else:
            self.connected_to_data_trace = False
            self.connect_video_to_data_trace_button.setText("Connect to Data")
        self.ConnectToDataTrace.emit(self.connected_to_data_trace)

    def rotate_frame(self, frame):
        if self.rotation_angle == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation_angle == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation_angle == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            return frame

    def rotate_video(self):
        if self.captured_video is not None:
            self.rotation_angle = (self.rotation_angle + 90) % 360
            self.change_frame(self.current_frame)

    def _reset_video_viewer(self):
        self.image_view.clear()
        self.set_button_state(True)

        # Initialize video variables
        self.video_file = ""
        self.video_frame = None
        self.video_frame_rate = None
        self.current_frame = 0
        self.total_frames = 0
        self.captured_video = None
        self.ms_per_frame = [1, 10, 15, 30, 60, 90]
        self.ms_per_frame_base = 30
        self.ms_per_frame_id = 3
        self.is_tiff = False
        self.connected_to_data_trace = False
        self.fps = None

        # Create a timer to update the video frames
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        # Initialize rotation variables
        self.rotation_angle = 0

    def close_file(self):
        if self.is_tiff:
            # Close the TIFF file
            self.captured_video.close()
        else:
            self.captured_video.release()
        # cv2.destroyAllWindows()

    def closeEvent(self, event):
        if self.captured_video is not None:
            self.close_file()
            self._reset_video_viewer()

#
# class VideoViewerQT(QMainWindow):
#     FrameChanged = pyqtSignal()
#     VideoLoaded = pyqtSignal()
#     ConnectToDataTrace = pyqtSignal(bool)
#
#     def __init__(self):
#         super().__init__()
#
#         self.setWindowTitle("Video Viewer")
#         self.setGeometry(100, 100, 800, 600)
#         self.setMinimumSize(800, 600)
#
#         # Create the main widget and layout
#         self.central_widget = QWidget(self)
#         self.setCentralWidget(self.central_widget)
#         self.layout = QVBoxLayout(self.central_widget)
#
#         # Create the video frame viewer
#         self.video_label = QLabel(f'Please Open A Video File')
#         self.speed_label = QLabel('')
#
#         self.video_widget = QVideoWidget(self)
#
#         # self.layout.addWidget(self.video_label)
#         # self.layout.addWidget(self.speed_label)
#         self.layout.addWidget(self.video_widget)
#
#         # Create the control widgets
#         self.controls_layout = QVBoxLayout()
#         self.control_button_layout = QHBoxLayout()
#
#         # Buttons
#         self.open_button = QPushButton("Open Video", self)
#         self.open_button.clicked.connect(self.open_file_dialog)
#         self.control_button_layout.addWidget(self.open_button)
#
#         self.play_button = QPushButton("Play", self)
#         self.play_button.clicked.connect(self.play_video)
#         self.control_button_layout.addWidget(self.play_button)
#
#         self.pause_button = QPushButton("Pause", self)
#         self.pause_button.clicked.connect(self.pause_video)
#         self.control_button_layout.addWidget(self.pause_button)
#
#         self.stop_button = QPushButton("Stop", self)
#         self.stop_button.clicked.connect(self.stop_video)
#         self.control_button_layout.addWidget(self.stop_button)
#
#         self.faster_button = QPushButton("Faster", self)
#         # self.faster_button.clicked.connect(self.speed_up)
#         self.control_button_layout.addWidget(self.faster_button)
#
#         self.slower_button = QPushButton("Slower", self)
#         # self.slower_button.clicked.connect(self.slow_down)
#         self.control_button_layout.addWidget(self.slower_button)
#
#         self.rotate_button = QPushButton("Rotate", self)
#         # self.rotate_button.clicked.connect(self.rotate_video)
#         self.control_button_layout.addWidget(self.rotate_button)
#
#         self.connect_video_to_data_trace_button = QPushButton("Connect to Data", self)
#         # self.connect_video_to_data_trace_button.clicked.connect(self.connect_to_data_trace)
#         self.control_button_layout.addWidget(self.connect_video_to_data_trace_button)
#
#         # Slider
#         self.frame_slider = QSlider(Qt.Orientation.Horizontal, self)
#         self.frame_slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
#         self.frame_slider.setTickInterval(1)
#         self.frame_slider.valueChanged.connect(self.change_frame)
#
#         self.control_button_layout.addWidget(self.frame_slider)
#
#         self.current_frame_label = QLabel("Current Frame: 0", self)
#         self.control_button_layout.addWidget(self.current_frame_label)
#
#         self.controls_layout.addWidget(self.frame_slider)
#         self.controls_layout.addLayout(self.control_button_layout)
#         self.layout.addLayout(self.controls_layout)
#
#         # Disabled Buttons for start up
#         self.set_button_state(True)
#         self.media_player = QMediaPlayer()
#         self.media_player.setVideoOutput(self.video_widget)
#         self.media_player.positionChanged.connect(self.update_position)
#         self.media_player.durationChanged.connect(self.update_duration)
#         # self.mediaPlayer.playbackStateChanged.connect(self.mediaStateChanged)
#         # self.mediaPlayer.errorChanged.connect(self.handleError)
#
#     def open_file_dialog(self):
#         input_file, _ = QFileDialog.getOpenFileName(
#             self, "Select Input File", "",
#             "Video Files (*.mp4; *.avi; *.mkv; *.mpeg; *.mpg; *.tif; *.tiff *.TIF; *.TIFF)")
#         if input_file:
#             self._load_video(input_file)
#
#     def _load_video(self, video_file):
#         self.video_file = video_file
#         self.current_frame = 0
#         self.total_frames = 0
#         self.media_player.setSource(QUrl.fromLocalFile(self.video_file))
#         self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
#         # Activate Buttons (False: Show Buttons)
#         self.set_button_state(False)
#         self.VideoLoaded.emit()
#
#     def set_button_state(self, state):
#         self.frame_slider.setDisabled(state)
#         self.play_button.setDisabled(state)
#         self.pause_button.setDisabled(state)
#         self.stop_button.setDisabled(state)
#         self.rotate_button.setDisabled(state)
#         self.faster_button.setDisabled(state)
#         self.slower_button.setDisabled(state)
#         self.connect_video_to_data_trace_button.setDisabled(state)
#
#     def play_video(self):
#         if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState or self.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
#             self.media_player.play()
#             print('PLAY')
#
#     def pause_video(self):
#         if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
#             self.media_player.pause()
#
#     def stop_video(self):
#         if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
#             self.media_player.stop()
#
#     def change_frame(self, frame):
#         self.media_player.setPosition(frame)
#
#     def connect_to_data_trace(self):
#         if not self.connected_to_data_trace:
#             self.connected_to_data_trace = True
#             self.connect_video_to_data_trace_button.setText("Disconnect")
#         else:
#             self.connected_to_data_trace = False
#             self.connect_video_to_data_trace_button.setText("Connect to Data")
#         self.ConnectToDataTrace.emit(self.connected_to_data_trace)
#
#     def update_position(self, position):
#         self.frame_slider.setValue(position)
#
#     def update_duration(self, duration):
#         self.frame_slider.setRange(0, duration)
#
#     def set_position(self, position):
#         self.media_player.setPosition(position)
