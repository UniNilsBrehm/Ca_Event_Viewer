from pathlib import Path
from PyQt6.QtCore import Qt
import pyqtgraph as pg


class Settings:
    temp_dir = Path('temp/')
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
