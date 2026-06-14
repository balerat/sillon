# Quantum Gas Magnifier
This repository goal is to concatenate all script and code for analyzing data for the quantum gas magnifier experiment. It structures is as follows:

## File structure:
- **core**: location of all main functions for each script
  - **fiting**: All the functions related to fitting such as the optimizer and data processing
  - **octogon**: rms calculation, potential extraction, population calculation
- **lib**: functions and classes vastly used for precessing the expriment data (Shots) and used in many other data analysis script in the lab
- **dev_notebook**: Notebook use for the development of the script, can be used for testing
- **old_method**: old method to calculate the rms and fitting to compare
- **potential_extractor**: New fitting and rms calulation code
- **potential_extractor_lab**: Jupyter notebook to analyze shot by shot the fitting and test stuff.

### TO DO:
- [x] Sparse Matrix
- [x] take multiple shots in account
- [x] pprint and verbose
- [x] test filters on new data
- [x] First chek alpha deform and shift
- [x] plot all fits
- [x] saving file in npy
- [ ] pcolor verbose
- [x] more speed for population function
- [ ] Add docstring
- [x] Added posibility for different filters
- [x] rework param
- [x] single shot notebook
- [ ] better magnification
- [x] filter noise when extracting rms
- [x] Bounds in main script
- [ ] Window for fit
- [x] better cost function
- [ ] Stretch for pop
- [ ] Better wa of peaking pop


## To do plots:

- [ ] Check means and density region for octogons
- [ ] Check 1st and 2nd order line of octogon
- [x] Different cutoff plot
- [x] two point bose glass comparaison
- [x] RMS regarding theta
