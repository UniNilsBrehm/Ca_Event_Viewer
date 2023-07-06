import numpy as np
from scipy.optimize import curve_fit
from PyQt6.QtCore import pyqtSignal, QObject
from settings import Settings
from IPython import embed
"""
Data Structure:
.
├── roi 1
│   ├── data_traces
:   │       ├── raw   
    │       :
    │       └── df
    └── events
            ├── event 1
            :   ├── tau rise
                :
                └── tau decay
                
Meta-Data Structure:
.
├── sampling_rate
├── meta_data
├── roi_list
├── stimulus
│   ├── available
:   ├── values
:   ├── time
:   ├── start
:   ├── end
:   ├── info

:   │       ├── raw   
    │       :
    │       └── df
    └── events
            ├── event 1
            :   ├── tau rise
                :
                └── tau decay
"""


class DataHandler(QObject):
    signal_roi_id_changed = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)
        # Create a dictionary where each roi is a key with a default dictionary that will later contain all the data
        self.data_traces_key = 'data_traces'
        self.events_key = 'events'
        self.data = None
        self.meta_data = dict()
        self.meta_data['meta_data'] = None
        self.meta_data['sampling_rate'] = None
        self.meta_data['roi_list'] = None
        self.meta_data['stimulus'] = dict()
        self.meta_data['stimulus']['available'] = False
        self.data_name = None
        self.roi_id = None
        self.time_axis = None
        self.fbs_per = Settings.fbs_percentile
        # Filter Settings
        self.filter_window = None
        self.filtered_trace = None
        self.data_norm_mode = 'raw'
        self.fitter = ExpFitter()
        self.single_traces = []

    def convert_events_to_csv(self):
        all_events = []
        for roi in self.meta_data['roi_list']:
            if self.get_events_count(roi_id=roi) > 0:
                events = self.get_roi_events(roi_id=roi)
                for key in events:
                    event = events[key].copy()
                    # Remove the pen information
                    del event['fit_rise_time']
                    del event['fit_decay_time']
                    del event['fit_rise_y']
                    del event['fit_decay_y']
                    del event['pen_color']
                    del event['pen_darker_color']
                    del event['hover_pen_color']
                    event['roi'] = roi
                    event['event'] = key
                    event['f_base_line'] = self.data[roi][self.data_traces_key]['fbs']
                    event['fbs_percentile'] = self.fbs_per

                    if self.meta_data['meta_data'] is not None:
                        event.update(self.meta_data['meta_data'])
                    all_events.append(event)
        return all_events

    def add_meta_data(self, meta_data):
        self.meta_data['meta_data'] = meta_data

    def compute_noise_statistics(self, p=5):
        if self.data is not None:
            roi_stats = dict()
            for roi in self.meta_data['roi_list']:
                traces = self.get_roi_data_traces(roi_id=roi)
                stats = dict()
                for key in traces:
                    if key == 'fbs' or key.startswith('filter'):
                        continue
                    trace = traces[key]
                    noise = trace[trace <= np.percentile(trace, p, axis=0)]
                    noise_mean = np.mean(noise, axis=0)
                    noise_sd = np.std(noise, axis=0)
                    stats[f'{key}_mean'] = noise_mean
                    stats[f'{key}_sd'] = noise_sd
                roi_stats[roi] = stats
            return roi_stats

    def add_stimulus_trace(self, trace, time, onset_times):
        self.meta_data['stimulus'] = dict()
        self.meta_data['stimulus']['available'] = True
        self.meta_data['stimulus']['values'] = trace
        self.meta_data['stimulus']['time'] = time
        self.meta_data['stimulus']['start'] = onset_times['start'].to_numpy()
        self.meta_data['stimulus']['end'] = onset_times['end'].to_numpy()
        self.meta_data['stimulus']['info'] = onset_times.iloc[:, 2].to_numpy()

    def moving_average_filter(self):
        if self.data is not None and self.filter_window is not None:
            win = int(self.filter_window * self.meta_data['sampling_rate'])
            data = self.data[self.roi_id][self.data_traces_key][self.data_norm_mode]
            if win > 0:
                filtered_data = np.convolve(data, np.ones(win) / win, mode='same')
                self.data[self.roi_id][self.data_traces_key]['filtered'] = filtered_data
                self.filtered_trace = filtered_data
            else:
                self.data[self.roi_id][self.data_traces_key]['filtered'] = data
                self.filtered_trace = data

    def get_filtered_trace(self, roi_id, norm_mode):
        if self.data is not None and self.filter_window is not None:
            win = int(self.filter_window * self.meta_data['sampling_rate'])
            trace = self.data[roi_id][self.data_traces_key][norm_mode]
            if win > 0:
                filtered_data = np.convolve(trace, np.ones(win) / win, mode='same')
                return filtered_data
            else:
                return None

    def add_single_trace(self, trace_time, trace_values):
        self.single_traces.append({'time': trace_time, 'values': trace_values})

    def add_data_trace(self, data_trace, data_trace_name, roi_id):
        self.data[roi_id][self.data_traces_key][data_trace_name] = data_trace

        # Compute delta f over f
        fbs, data_df = self._to_df_over_f(raw_data=data_trace)
        self.data[roi_id][self.data_traces_key]['fbs'] = fbs
        self.data[roi_id][self.data_traces_key]['df'] = data_df

        # Compute z score
        z_score = self._to_z_score(data_df)
        self.data[roi_id][self.data_traces_key]['z'] = z_score

        # Compute min max norm
        min_max_norm = self._to_min_max(raw_data=data_trace)
        self.data[roi_id][self.data_traces_key]['min_max'] = min_max_norm

    @staticmethod
    def _to_min_max(raw_data):
        # x = (x- min(x)) / (max(x)-min(x))
        data_min_max = (raw_data - np.min(raw_data)) / (np.max(raw_data) - np.min(raw_data))
        return data_min_max

    def _to_df_over_f(self, raw_data):
        fbs = np.percentile(raw_data, self.fbs_per, axis=0)
        data_df = (raw_data - fbs) / fbs
        return fbs, data_df

    @staticmethod
    def _to_z_score(data):
        z_score = (data - np.mean(data)) / np.std(data)
        return z_score

    def get_roi_index(self):
        roi_index = np.where(self.roi_id == np.array(self.meta_data['roi_list']))[0][0]
        return roi_index

    def change_roi(self, new_roi):
        self.roi_id = new_roi
        self.signal_roi_id_changed.emit()

    @staticmethod
    def convert_samples_to_time(data_size, fr):
        max_time = data_size / fr
        time_steps = np.linspace(0, max_time, data_size)
        return time_steps

    def get_time_axis(self, roi_id):
        data_size = self.data[roi_id]['data_traces']['raw'].shape[0]
        self.time_axis = self.convert_samples_to_time(data_size, self.meta_data['sampling_rate'])
        return self.time_axis

    def create_new_data_set(self, roi_list, data_name, sampling_rate):
        # Create an empty data set
        self.meta_data['roi_list'] = roi_list
        self.data = dict().fromkeys(roi_list)
        for key in self.data:
            self.data[key] = {self.data_traces_key: {}, self.events_key: {}}
        self.data_name = data_name
        self.meta_data['sampling_rate'] = sampling_rate

    def get_roi_count(self):
        if self.meta_data['roi_list'] is not None:
            return len(self.meta_data['roi_list'])
        else:
            return 0

    def add_event(self, event_data, roi_id):
        # Reset keys (renumerate)
        self.data[roi_id][self.events_key] = {i: v for i, v in enumerate(self.data[roi_id][self.events_key].values())}

        cc = self.get_events_count(roi_id)
        if cc == 0:
            event_id = 0
        else:
            event_id = cc
        self.data[roi_id][self.events_key][event_id] = event_data

    def get_event(self, roi_id, event_id):
        try:
            event = self.data[roi_id][self.events_key][event_id]
        except KeyError:
            event = None
        return event

    def get_roi_events(self, roi_id):
        return self.data[roi_id][self.events_key]

    def get_data(self, roi_id=-1):
        if roi_id == -1:
            # return the entire data set
            return self.data
        else:
            # return data for this roi
            return self.data[roi_id]

    def remove_all_roi_data_traces(self, roi_id):
        del self.data[roi_id][self.data_traces_key]

    def remove_data_trace(self, data_trace_name, roi_id):
        try:
            del self.data[roi_id][self.data_traces_key][data_trace_name]
        except KeyError:
            pass

    def remove_event(self, roi_id, event_id):
        try:
            del self.data[roi_id][self.events_key][event_id]
            # Reset keys (renumerate)
            self.data[roi_id][self.events_key] = {i: v for i, v in enumerate(self.data[roi_id][self.events_key].values())}
        except KeyError:
            pass

    def get_events_count(self, roi_id):
        return len(self.data[roi_id][self.events_key])

    def get_data_traces_count(self, roi_id):
        return len(self.data[roi_id][self.data_traces_key])

    def get_roi_data_traces(self, roi_id):
        return self.data[roi_id][self.data_traces_key]

    def load_new_data_set(self, data, meta_data):
        self.data = data
        self.meta_data = meta_data


class ExpFitter:
    @staticmethod
    def decay_func(xx, x_tau):
        # return (np.max(y)-np.min(y)) * np.exp(-(xx / x_tau)) + np.min(y)
        # return a * np.exp(-(xx / x_tau)) + c
        return np.exp(-(xx / x_tau))

    @staticmethod
    def rise_func(xx, x_tau):
        # return x_tau2 * xx + max_y
        # return (np.max(y)-np.min(y)) * (1 - np.exp(-(xx / x_tau))) + np.min(y)
        # return a * (1 - np.exp(-(xx / x_tau))) + c
        return 1 - np.exp(-(xx / x_tau))

    @staticmethod
    def double_func(xx, tau1, tau2):
        # return (1 - np.exp(-(xx / tau1))) * np.exp(-(xx / tau2)) * np.max(y) + np.min(y)
        return (1 - np.exp(-(xx / tau1))) * np.exp(-(xx / tau2))

    def fit_rise(self, x, y):
        lower_bounds = 0.01
        upper_bounds = 60
        # x_fitted = np.linspace(0, np.max(x_zeroed), 1000)
        popt, pcov = curve_fit(self.rise_func, x, y, bounds=[lower_bounds, upper_bounds])
        tau_value = popt[0]
        # aa = popt[1]
        # cc = popt[2]
        # y_fitted = self.rise_func(x_fitted, tau_value, aa, cc)
        p_value = np.sqrt(np.diag(pcov))[0]
        return tau_value, p_value

    def fit_decay(self, x, y):
        lower_bounds = 0.01
        upper_bounds = 60
        popt, pcov = curve_fit(self.decay_func, x, y, bounds=[lower_bounds, upper_bounds])
        tau_value = popt[0]
        # aa = popt[1]
        # cc = popt[2]
        p_value = np.sqrt(np.diag(pcov))[0]
        return tau_value, p_value

    def fit_event(self, x, y, idx):
        # First the Rise Phase
        rise_y = y[idx[0]:idx[1]]
        rise_x = x[idx[0]:idx[1]]

        # set x start time to zero
        rise_x = rise_x - rise_x[0]

        # normalize y to 0 - 1:
        rise_y = (rise_y - np.min(rise_y)) / (np.max(rise_y)-np.min(rise_y))

        # Now Run the Fit
        rise_tau, rise_p = self.fit_rise(rise_x, rise_y)

        # Get a curve for the fitted values
        fit_rise_y = self.rise_func(rise_x, rise_tau)

        # Now the Decay Phase
        decay_y = y[idx[1]:idx[2]]
        decay_x = x[idx[1]:idx[2]]

        # set x start time to zero
        decay_x = decay_x - decay_x[0]

        # normalize y to 0 - 1:
        decay_y = (decay_y - np.min(decay_y)) / (np.max(decay_y)-np.min(decay_y))

        # Now Run the Fit
        decay_tau, decay_p = self.fit_decay(decay_x, decay_y)

        # Get a curve for the fitted values
        fit_decay_y = self.decay_func(decay_x, decay_tau)
        result = {
            'fit_rise_time': rise_x,
            'fit_rise_y': fit_rise_y,
            'fit_rise_tau': rise_tau,
            'fit_rise_error': rise_p,
            'fit_decay_time': decay_x,
            'fit_decay_y': fit_decay_y,
            'fit_decay_tau': decay_tau,
            'fit_decay_error': decay_p,
        }
        return result
