# Main Features

- Menus for entering parameters (manually or from a text file), materials, geometries, sources, and monitors 
- A domain preview window which updates itself automatically upon geometry changes
- Basic parameter sweeps 
- Common analyses in photonics: harminv mode extraction, field patterns/animations (for both time and frequency-domain), MPB (band structures and fields), transmission spectra (supports recycling cached reference run data), k-point runs
- Project serialization via YAML file import/export
- Simulations can either be run on the application, or a Python script which is generated according to GUI actions
- Results are viewed in an output window, and can be exported

screenshot goes here
# How to run
For now, the application can be ran by first creating a Conda environment (the most convenient way to install Meep) with the relevant packages:
```
conda create --name meep-gui --override-channels -c conda-forge python=3.11
conda activate meep-gui
conda install --override-channels -c conda-forge \
  pymeep mpb pyqt numpy matplotlib pyyaml ffmpeg
```

Then, in the folder, to run the application:

```
python3 app.y
```
In the future, MacOS and Linux executables could be created.
# WIP
This arose from a research tool, and the application is still in its early phases. As such, there are a number of planned features:
- More material types rather than simple dielectrics, such as common dispersion models, chi2/3 nonlinearities, and conductivity
- GDS import and more geometry primitives (provided by builtin Meep functions)
- Executables from PyInstaller for MacOS and certain Linux distros
- Fixing the PyQt issue of not seeing animations in the output window
- Fixing the stop button, potentially by using a ```
run(..., until=button click) ``` condition


