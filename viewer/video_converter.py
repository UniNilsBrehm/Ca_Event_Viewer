from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel, QCheckBox,\
    QComboBox, QApplication, QDoubleSpinBox
from IPython import embed
import ffmpy
import os
import subprocess


class VideoConverter(QMainWindow):

    ffmpeg_dir_set = pyqtSignal()

    # Using subprocess to run a terminal command using a string
    # Or using the ffmpeg package
    def __init__(self, convert_settings):
        super().__init__()

        self.settings = convert_settings
        self.input_file = None
        self.output_file = None

        self.crf_value = 17
        self.preset = 'superfast'
        self.output_frame_rate = 0

        # Create a central widget and layout
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        # Create a button for browsing files
        self.browse_button = QPushButton("Browse Files")
        self.browse_button.clicked.connect(self.browse_files)

        self.input_file_label = QLabel('Input File not selected')
        self.output_file_label = QLabel('Output File not selected')

        self.start_button = QPushButton("Convert Video")
        self.start_button.clicked.connect(self.start_converting)

        self.extract_frames_button = QPushButton("Extract Frames")
        self.extract_frames_button.clicked.connect(self.start_extracting_frames)

        self.change_ffmpeg_dir_button = QPushButton("Set ffmpeg directory")
        self.change_ffmpeg_dir_button.clicked.connect(self.browse_file_ffmpeg)

        self.ffmpeg_dir_label = QLabel(f'ffmpeg at: {self.settings.settings_file.loc["ffmpeg"].item()}')

        # Settings
        self.use_gpu = False
        gpu_check_box_layout = QHBoxLayout()
        self.gpu_check_box = QCheckBox()
        self.gpu_check_box.setCheckState(Qt.CheckState.Unchecked)
        self.gpu_check_box.stateChanged.connect(self.get_gpu_state)
        self.gpu_check_box_label = QLabel('Use GPU')
        gpu_check_box_layout.addWidget(self.gpu_check_box_label)
        gpu_check_box_layout.addWidget(self.gpu_check_box)

        supress_terminal_output_layout = QHBoxLayout()
        self.supress_terminal_output = True
        self.supress_terminal_output_check_box = QCheckBox()
        self.supress_terminal_output_check_box.setCheckState(Qt.CheckState.Checked)
        self.supress_terminal_output_check_box.stateChanged.connect(self.get_supress_state)
        self.supress_terminal_output_label = QLabel('Supress Terminal Output')
        supress_terminal_output_layout.addWidget(self.supress_terminal_output_label)
        supress_terminal_output_layout.addWidget(self.supress_terminal_output_check_box)

        self.quality_combo_box = QComboBox()
        self.quality_combo_box.addItem('superfast')
        self.quality_combo_box.addItem('medium')
        self.quality_combo_box.addItem('slower')
        self.quality_combo_box_label = QLabel('Compression Preset')

        self.constant_rate_factor = QDoubleSpinBox()
        self.constant_rate_factor.setValue(self.crf_value)
        self.constant_rate_factor_label = QLabel('Video Quality: CRF (visually lossless=17, technically lossless=0)(range: 0-51)')

        self.change_frame_rate = QDoubleSpinBox()
        self.change_frame_rate.setValue(0)
        self.change_frame_rate_label = QLabel('Output Frame Rate (Hz) (will be ignored if set to 0)')

        self.status_label = QLabel('Ready')

        layout.addWidget(self.browse_button)
        layout.addWidget(self.input_file_label)
        layout.addWidget(self.output_file_label)
        layout.addWidget(self.change_ffmpeg_dir_button)
        layout.addSpacing(10)
        layout.addWidget(self.ffmpeg_dir_label)
        layout.addSpacing(20)
        layout.addLayout(gpu_check_box_layout)
        layout.addSpacing(5)
        layout.addLayout(supress_terminal_output_layout)
        layout.addSpacing(10)
        layout.addWidget(self.quality_combo_box_label)
        layout.addSpacing(5)
        layout.addWidget(self.quality_combo_box)
        layout.addSpacing(20)
        layout.addWidget(self.constant_rate_factor_label)
        layout.addSpacing(5)
        layout.addWidget(self.constant_rate_factor)
        layout.addSpacing(20)
        layout.addWidget(self.change_frame_rate_label)
        layout.addSpacing(5)
        layout.addWidget(self.change_frame_rate)
        layout.addSpacing(20)
        layout.addWidget(self.start_button)
        layout.addSpacing(10)
        layout.addWidget(self.extract_frames_button)
        layout.addSpacing(10)
        layout.addWidget(self.status_label)

        # Set the central widget and window properties
        self.setCentralWidget(central_widget)
        self.setWindowTitle("Video Converter")

        if self.settings.settings_file.loc['ffmpeg'].item() == 'NaN':
            self.browse_file_ffmpeg()
        self.ffmpeg_dir = self.settings.settings_file.loc['ffmpeg'].item()
        self.ffmpeg_probe = f'{os.path.split(self.ffmpeg_dir)[0]}/ffprobe.exe'
        self._define_ffmpeg_settings()

    def _define_ffmpeg_settings(self):
        self.ffmpeg_input_opt = {'gpu': ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'], 'cpu': None}

        # Get Values
        self.crf_value = int(self.constant_rate_factor.value())
        self.preset = self.quality_combo_box.currentText()
        self.output_frame_rate = int(self.change_frame_rate.value())

        if self.crf_value > 51:
            self.crf_value = 51

        if self.output_frame_rate > 0:
            self.ffmpeg_output_opt = {
                'gpu': ['-c:v', 'h264_nvenc', '-preset', self.preset, '-qp', str(self.crf_value), '-filter:v', f'fps={self.output_frame_rate}'],
                'cpu': ['-c:v', 'libx264', '-preset', self.preset, '-crf', str(self.crf_value), '-filter:v', f'fps={self.output_frame_rate}'],
                'avi': ['-an', '-vcodec', 'rawvideo', '-y']
            }
        else:
            self.ffmpeg_output_opt = {
                'gpu': ['-c:v', 'h264_nvenc', '-preset', self.preset, '-qp', str(self.crf_value)],
                'cpu': ['-c:v', 'libx264', '-preset', self.preset, '-crf', str(self.crf_value)],
                'avi': ['-an', '-vcodec', 'rawvideo', '-y']
            }

        self.ffmpeg_global_opt = {
            'supress': ['-y', '-loglevel', 'quiet'],
            'show': ['-y'],
        }

    def get_gpu_state(self):
        if self.gpu_check_box.checkState() == Qt.CheckState.Checked:
            self.use_gpu = True
        else:
            self.use_gpu = False

    def get_supress_state(self):
        if self.supress_terminal_output_check_box.checkState() == Qt.CheckState.Checked:
            self.supress_terminal_output = True
        else:
            self.supress_terminal_output = False

    def get_video_info(self, filename):
        result = subprocess.run([self.ffmpeg_probe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=duration:stream=avg_frame_rate", "-of",
                                 "default=noprint_wrappers=1:nokey=1", filename],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        output = result.stdout.decode("utf-8").split('\r\n')
        frame_rate = float(output[0].split('/')[0])  # Extracting the first part before '/'
        duration = float(output[1])

        return frame_rate, duration

    # def get_video_duration(self, filename):
    #     # gets video duration in seconds using ffmpeg probe
    #     result = subprocess.run([self.ffmpeg_probe, "-v", "error", "-show_entries",
    #                              "format=duration", "-of",
    #                              "default=noprint_wrappers=1:nokey=1", filename],
    #                             stdout=subprocess.PIPE,
    #                             stderr=subprocess.STDOUT)
    #     return float(result.stdout)

    def extract_frames(self, input_file, save_dir):
        if self.ffmpeg_dir is not None:
            # ffmpeg -i input.mp4 -vf fps=1 %04d.png
            video_frame_rate, video_duration = self.get_video_info(input_file)

            if self.output_frame_rate > 0:
                output_cmd = ['-vf', f'fps={self.output_frame_rate}']
                fr = self.output_frame_rate
            else:
                output_cmd = None
                fr = video_frame_rate

            number_of_frames = int(fr * video_duration)
            print(f'++++ Expecting to Store {number_of_frames} Frames to HDD+++')
            counter = len(str(number_of_frames)) + 1
            output_dir = f'{save_dir}/%0{counter}d.jpg'
            if self.supress_terminal_output:
                global_settings = self.ffmpeg_global_opt['supress']
            else:
                global_settings = self.ffmpeg_global_opt['show']

            ff = ffmpy.FFmpeg(
                executable=self.ffmpeg_dir,
                global_options=global_settings,
                inputs={input_file: None},
                outputs={output_dir: output_cmd}
            )
            ff.run()

    def start_extracting_frames(self):
        file_dir = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        if self.input_file is not None and file_dir is not None:
            print('START EXTRACTING')
            # self._define_ffmpeg_settings()
            self.output_frame_rate = int(self.change_frame_rate.value())
            self.please_wait_status()
            QApplication.processEvents()
            self.extract_frames(self.input_file, file_dir)
            self.finished_status()

    def convert_video(self, input_file, output_file):
        if self.ffmpeg_dir is not None:
            # check settings
            # speed = self.quality_combo_box.currentText()
            if self.use_gpu:
                hw = 'gpu'
            else:
                hw = 'cpu'

            if output_file[-3:] == 'avi':
                # Use no compression for avi file (otherwise you can not open it in imagej)
                input_cmd = self.ffmpeg_input_opt['cpu']
                output_cmd = self.ffmpeg_output_opt['avi']
            else:
                input_cmd = self.ffmpeg_input_opt[hw]
                output_cmd = self.ffmpeg_output_opt[hw]

            if self.supress_terminal_output:
                global_settings = self.ffmpeg_global_opt['supress']
            else:
                global_settings = self.ffmpeg_global_opt['show']

            ff = ffmpy.FFmpeg(
                executable=self.ffmpeg_dir,
                global_options=global_settings,
                inputs={input_file: input_cmd},
                outputs={output_file: output_cmd}
            )
            ff.run()

    def browse_file_ffmpeg(self):
        self.ffmpeg_dir, _ = QFileDialog.getOpenFileName(self, "Select FFMPEG .exe", "", "ffmpeg (*.exe)")
        self.settings.modify_setting('ffmpeg', self.ffmpeg_dir)
        self.settings.save_settings()
        self.ffmpeg_dir_label.setText(f'ffmpeg at: {self.ffmpeg_dir}')

    def please_wait_status(self):
        self.status_label.setText('Please wait ... ')
        self.browse_button.setDisabled(True)
        self.change_ffmpeg_dir_button.setDisabled(True)

    def finished_status(self):
        self.status_label.setText('Converting finished!')
        self.browse_button.setDisabled(False)
        self.change_ffmpeg_dir_button.setDisabled(False)
        if not self.supress_terminal_output:
            print('')
            print('++++ FINISHED ++++')
            print('')

    def browse_files(self):
        # if self.settings.settings_file.loc['ffmpeg'].item() == 'NaN':
        #     self.browse_file_ffmpeg()
        # self.ffmpeg_dir = self.settings.settings_file.loc['ffmpeg'].item()
        # self.please_wait_status()
        input_file, _ = QFileDialog.getOpenFileName(
            self, "Select Input File", "", "Video Files (*.mp4; *.avi; *.mkv; *.mpeg; *.mpg)")
        if input_file:
            self.input_file = input_file
            self.input_file_label.setText(input_file)
            # output_file, _ = QFileDialog.getSaveFileName(
            #     self, "Select Output File", "", "MP4, (*.mp4);; AVI, (*.avi);; MKV, (*.mkv)")
            # if output_file:
            #     self.output_file = output_file
            #     self.input_file_label.setText(input_file)
            #     self.output_file_label.setText(output_file)
            #     # self.convert_video(input_file, output_file)
            #     # self.finished_status()

    def start_converting(self):
        output_file, _ = QFileDialog.getSaveFileName(
            self, "Select Output File", "", "MP4, (*.mp4);; AVI, (*.avi);; MKV, (*.mkv)")
        if output_file:
            self.output_file = output_file
            self.output_file_label.setText(output_file)

        if self.input_file is not None and self.output_file is not None:
            self._define_ffmpeg_settings()
            self.please_wait_status()
            QApplication.processEvents()
            self.convert_video(self.input_file, self.output_file)
            self.finished_status()