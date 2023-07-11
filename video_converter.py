from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel, QCheckBox,\
    QComboBox, QApplication
from IPython import embed
import ffmpy


class VideoConverter(QMainWindow):

    ffmpeg_dir_set = pyqtSignal()

    # Using subprocess to run a terminal command using a string
    # Or using the ffmpeg package
    def __init__(self, convert_settings):
        super().__init__()

        self.settings = convert_settings
        self.input_file = None
        self.output_file = None

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
        self.quality_combo_box.addItem('fast')
        self.quality_combo_box.addItem('medium')
        self.quality_combo_box.addItem('slow')

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
        layout.addWidget(self.quality_combo_box)
        layout.addSpacing(20)
        layout.addWidget(self.start_button)
        layout.addSpacing(10)
        layout.addWidget(self.status_label)

        # Set the central widget and window properties
        self.setCentralWidget(central_widget)
        self.setWindowTitle("Video Converter")

        self.ffmpeg_dir = None
        self._define_ffmpeg_settings()

    def _define_ffmpeg_settings(self):
        self.ffmpeg_input_opt = {'gpu': ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'], 'cpu': None}

        self.ffmpeg_output_opt = {
            'gpu': {
                'fast': ['-c:v', 'h264_nvenc', '-preset', 'superfast', '-qp', '17'],
                'medium': ['-c:v', 'h264_nvenc', '-preset', 'medium', '-qp', '17'],
                'slow': ['-c:v', 'h264_nvenc', '-preset', 'slower', '-qp', '17'],
            },
            'cpu': {
                'fast': ['-c:v', 'libx264', '-preset', 'superfast', '-crf', '17'],
                'medium': ['-c:v', 'libx264', '-preset', 'medium', '-crf', '17'],
                'slow': ['-c:v', 'libx264', '-preset', 'slower', '-crf', '17'],
            }
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

    def convert_video(self, input_file, output_file):
        if self.ffmpeg_dir is not None:
            # check settings
            speed = self.quality_combo_box.currentText()
            if self.use_gpu:
                hw = 'gpu'
            else:
                hw = 'cpu'
            input_cmd = self.ffmpeg_input_opt[hw]
            output_cmd = self.ffmpeg_output_opt[hw][speed]

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

    def browse_files(self):
        if self.settings.settings_file.loc['ffmpeg'].item() == 'NaN':
            self.browse_file_ffmpeg()
        self.ffmpeg_dir = self.settings.settings_file.loc['ffmpeg'].item()
        # self.please_wait_status()
        input_file, _ = QFileDialog.getOpenFileName(
            self, "Select Input File", "", "Video Files (*.mp4; *.avi; *.mkv; *.mpeg)")
        if input_file:
            self.input_file = input_file
            output_file, _ = QFileDialog.getSaveFileName(
                self, "Select Output File", "", "MP4, (*.mp4);; AVI, (*.avi);; MKV, (*.mkv)")
            if output_file:
                self.output_file = output_file
                self.input_file_label.setText(input_file)
                self.output_file_label.setText(output_file)
                # self.convert_video(input_file, output_file)
                # self.finished_status()

    def start_converting(self):
        if self.input_file is not None and self.output_file is not None:
            self.please_wait_status()
            QApplication.processEvents()
            self.convert_video(self.input_file, self.output_file)
            self.finished_status()
