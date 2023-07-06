# CaEventAnalyzer
Welcome to the experimental branch of the <i>CaEventViewer</i>.
With the <i>CaEventViewer</i> you can plot and analyze calcium transients from Ca-imaging experiments.


## Installation
Before running the "viewer.py" file you should make sure that you have installed all the needed dependencies.
You can install the dependencies via pip or conda (Anaconda) like this:

```shell
pip install numpy
pip install pandas
pip install scipy
pip install PyQt6
pip install pyqtgraph
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

## Stimulus Representation
You can add a visual representation of the stimulus (rectangular function) by importing a .csv file. It must have the following strucutre:
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

### ----------
Nils Brehm - 2023
