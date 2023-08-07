# CaEventViewer
Welcome toe <i>CaEventViewer</i>.
With the <i>CaEventViewer</i> you can plot and analyze calcium transients from Ca-imaging experiments.

## New Features
- Video/Tiff Viewer that can connect the video to the ROI Data Trace to visualize what is happening!
- Video File Converter based on FFMPEG and ffmpy
- Import single stimulus traces for each ROI (e.g. stimulus voltage trace); Must have the same format as the ROI data traces
- Save Figures (via right-click menu or via Toolbar)
- Fixed ROI Combo Box Bug

## Installation
Before running the "viewer.py" file you should make sure that you have installed all the needed dependencies.
You can manually install the dependencies via pip or conda (Anaconda) like this:

```shell
pip install numpy
pip install pandas
pip install scipy
pip install PyQt6
pip install pyqtgraph
pip install opencv-python
pip install ffmpy
```
Or you can use the "conda_env.yml" file to create an anaconda environment like this:\
Open you anaconda prompt (terminal) and navigate to the location of the "conda_env.yml" file.\
Then type:

```shell
conda env create -f conda_env.yml
```
Don't forget to activate your new environment:
```shell
conda activate viewer
```

To start the Viewer, open your <i>terminal</i> of choice and go to the directory containing the files.
Then run "main.py":

```shell
python main.py
```

## Data Files
You can import data stored in .csv (comma separated) files. The structure of this files must be like this:

| ROI_1         | ROI_2         | ... | ROI_n         |
|---------------|---------------|-----|---------------|
| x<sub>0</sub> | x<sub>0</sub> |     | x<sub>0</sub> |
| x<sub>1</sub> | x<sub>1</sub> |     | x<sub>1</sub> |
| : .           | : .           |     | : .           |
| x<sub>n</sub> | x<sub>n</sub> |     | x<sub>n</sub> |

Each column represents a ROI data trace (samples: x<sub>0</sub>-x<sub>n</sub>) and has a "header" with the ROI name.
Additionally, you will be asked to enter a sampling rate in Hz. Make sure to always use "." (dot) for decimal separation.

## Stimulus Traces individually for each ROI
For each ROI (column in your data trace) you can add an individual stimulus trace.
If you omit the "Time" column you will be asked to give a sampling dt in seconds so that a time axis can be computed automatically.

| Time          | ROI_1         | ROI_2         | ... | ROI_n         |
|---------------|---------------|---------------|-----|---------------|
| t<sub>0</sub> | s<sub>0</sub> | s<sub>0</sub> |     | s<sub>0</sub> |
| t<sub>1</sub> | s<sub>1</sub> | s<sub>1</sub> |     | s<sub>1</sub> |
| : .           | : .           | : .           |     | : .           |
| t<sub>n</sub> | s<sub>n</sub> | s<sub>n</sub> |     | s<sub>n</sub> |

## Stimulus Representation
You can add a visual representation of the stimulus (rectangular function) for all ROIS together by importing a .csv file. It must have the following strucutre:

| start | end | stimulus      |
|-------|-----|---------------|
| 10    | 15  | grating_90    |
| 30    | 40  | moving_target |

Each Row represents one stimulus presentation. It needs a start time (onset, in seconds) and an end time (offset, in seconds). Additionally, you can give a "stimulus" name to define the stimulus type.

## Adding Meta Data
It is possible to add custom entries like meta data to the output .csv file. The file can only have two rows but as many columns as needed.
A meta data file could look like this:

| date       | dob        | genotype | method     |
|------------|------------|----------|------------|
| 22.04.2023 | 19.04.2023 | abc:Gal4 | Ca-Imaging |

## Compute Noise Statistics
Via "File-->Compute Noise Statistics" you can export some statistics of the Noise in your data to a .csv file.
It will look at all data values that are smaller than the 5th percentile and returns the mean and the standard deviation of it.

## Analysing Events
By pressing the "Alt" ("command") Key you can enter the "event analyzer mode".

## Video Viewer
You can independently import a data trace (.csv) and a video (.mp4, .avi, .mkv) or tiff file

### ----------
Nils Brehm - 2023
