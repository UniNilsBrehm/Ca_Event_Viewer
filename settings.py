from pathlib import Path
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import pandas as pd
import os
# from IPython import embed


class SettingsFile:
    def __init__(self):
        f = os.listdir(os.getcwd())
        if 'settings.csv' in f:
            self.settings_file = pd.read_csv('settings.csv', index_col=0)
        else:
            self.settings_file = pd.DataFrame(columns=['Value'])
            self.settings_file.loc['ffmpeg'] = 'NaN'
            self.settings_file.loc['sampling_dt'] = 0.002
            self.settings_file.loc['stimulus_sampling_dt'] = 0.01666666666666
            self.settings_file.loc['fbs_percentile'] = 5
            self.settings_file.loc['temp_dir'] = '/'
            self.settings_file.loc['default_dir'] = 'C:/'

            self.settings_file.to_csv('settings.csv')

            # self.settings_file = dict()
            # self.settings_file['ffmpeg'] = ['NaN']
            # self.settings_file['sampling_dt'] = [0.002]
            # self.settings_file['stimulus_sampling_dt'] = [0.01666666666666]

            # Convert to pandas data frame
            # self.settings_file = pd.DataFrame.from_dict(self.settings_file).transpose()
            # self.settings_file.columns = ['Value']
            # self.settings_file.to_csv('settings.csv')

        # self.default_dir = Path(self.settings_file.loc['default_dir'])

    def save_settings(self):
        self.settings_file.to_csv('settings.csv')

    def modify_setting(self, index_name, value):
        self.settings_file.loc[index_name] = value


class Settings:
    default_dir = Path('C:/')
    # default_dir = Path('/home/leo/Nextcloud/Bio_B.Sc/6.Semester/Bachelorarbeit/')
    sampling_dt = 0.05
    sampling_rate = 1 / sampling_dt
    fbs_percentile = 5


class PyqtgraphSettings:
    # Global pyqtgraph settings
    pg.setConfigOption('background', pg.mkColor('w'))
    pg.setConfigOption('foreground', pg.mkColor('k'))
    # pg.setConfigOption('useOpenGL', True)
    pg.setConfigOption('antialias', False)
    pg.setConfigOption('imageAxisOrder', 'row-major')


class PlottingStyles:
    info_box_font_size = 8
    axis_width = 3
    axis_ticks_font_size = 16
    line_style = {'color': 'k', 'width': 1}
    line_style_transparent = {'color': pg.mkColor(180, 180, 180), 'width': 1}

    fit_rise_pen = pg.mkPen(color='r', width=2, style=Qt.PenStyle.DotLine)
    fit_rise_shadow_pen = pg.mkPen(color='k', width=4)
    fit_decay_pen = pg.mkPen(color='b', width=2, style=Qt.PenStyle.DotLine)
    fit_decay_shadow_pen = pg.mkPen(color='k', width=4)

    line_pen = pg.mkPen(line_style)
    line_pen_transparent = pg.mkPen(line_style_transparent)
    stimulus_pen = pg.mkPen(color='b')
    single_trace_pen = pg.mkPen(color='k')

    collecting_mode_bg = (255, 250, 250)
    line_filtered_pen = pg.mkPen({'color': 'r', 'width': 1})

    axis_label_styles = {'color': 'k', 'font-size': '20px'}
    point_brush = pg.mkBrush(color='c')
    done_point_brush = pg.mkBrush(color='g')
    collecting_points = {
        'pen': pg.mkPen(color='k'),
        'brush': pg.mkBrush(color='c'),
        'symbol': 'o',
        'size': 15,
        'hoverSymbol': 'o',
        'hoverSize': 25
    }
    # done_click_symbols = {
    #     'pen': pg.mkPen(color='k'),
    #     'symbol': 'x',
    #     'size': 10,
    #     'hoverSymbol': 'x',
    #     'hoverSize': 15
    # }
    tau_points_symbols = {
        'pen': pg.mkPen(color='k'),
        'brush': pg.mkBrush(color='m'),
        'symbol': 'o',
        'size': 15,
        'hoverSymbol': 'o',
        'hoverSize': 20
    }
    # click_symbols_brush = [pg.mkBrush(color='c'), pg.mkBrush(color='m'), pg.mkBrush(color='y')]
    # tau_points_brush = [pg.mkBrush(color='r'), pg.mkBrush(color='b')]
