# ASSS - A Solar System Simulator

A live, hackable Solar System simulator built on REBOUND. Real orbital mechanics, real measured black hole masses (LIGO/Virgo, Event Horizon Telescope), and a Python console built right into the app so you can script and test things while the simulation is running.

## Features

- Real-time N-body simulation of the Sun and 8 planets, with real orbital elements
- Full GUI: toolbar, live matplotlib view, right-click context menu, tabbed console/editor panel
- Mouse controls: drag to pan, scroll wheel to zoom, right-click for a context menu (copy positions, launch a comet, place a black hole, re-run loaded scripts, recenter/reset the view)
- Built-in Python console (REPL) with direct access to the running simulation (`sim`, `app`)
- Built-in script editor (IDLE-style) to write and run scripts against the live simulation, with optional handoff to real IDLE or Notepad++
- Comet launcher using real orbital mechanics (vis-viva equation + angular momentum) to set an exact perihelion and eccentricity
- Catalog of real black holes with measured masses (Sagittarius A*, M87*, TON 618, Cygnus X-1, GW150914, GW190521) that can be dropped into the simulation
- Position logging to CSV for later analysis, without interrupting the running simulation
- Performance: rendering uses blitting instead of full redraws, keeping the simulation loop cheap even on modest hardware

## Requirements

- Python 3.12+
- Packages: numpy, scipy, matplotlib, rebound, astropy, pandas
- Optional: Notepad++ (only needed for the "Create/Edit script (Notepad++)" button)

## Setup

```
python -m venv venv
venv\Scripts\pip install numpy scipy matplotlib jupyter rebound astropy pandas
```

## Usage

Run the main app from the project root:

```
venv\Scripts\python.exe notebooks\01_live_viewer.py
```

### Controls

- **Toolbar**: Pause/Resume, Reset, Record Log, Load script, Open in IDLE, Create/Edit script (Notepad++), speed slider
- **Mouse on the simulation**: left-drag to pan, scroll to zoom, right-click for the context menu
- **Right panel**: switch between the Console tab (interactive Python shell) and the Editor tab (write a script, Ctrl+Enter to run it)

The console and editor both run in the same namespace as the live simulation, so anything you type or run has immediate access to `sim` (the REBOUND simulation) and `app` (the running application instance).

## Project structure

```
notebooks/
  00_test_setup.py     basic REBOUND sanity check
  01_live_viewer.py     main application
  02_test_comet.py       example script: launch a comet with a chosen perihelion/eccentricity
  03_black_holes.py     loads the black hole catalog into the console
data/
  black_holes.json      real, sourced black hole masses
  logs/                 CSV position logs (created at runtime, not tracked in git)
```

## Black hole data sources

All masses in `data/black_holes.json` are real, measured values, not estimates made up for this project:

- Sagittarius A*: Event Horizon Telescope, stellar orbit measurements (S2/S0-2)
- M87*: Event Horizon Telescope (2019), first direct image of a black hole
- TON 618: quasar emission line correlation
- Cygnus X-1: radio astrometry and spectroscopy (Science, 2021)
- GW150914 and GW190521: LIGO/Virgo gravitational wave detections

Sources and methods are listed per entry in the JSON file.

## Known limitations

- The simulation uses REBOUND's WHFast integrator, tuned for the Sun and planets. Placing a very massive black hole (roughly 1000+ solar masses) close to the planets will make the simulation diverge within a few simulated years; the app warns before letting you do this.
- This is a Newtonian N-body simulation, not general relativity. It is useful for orbital mechanics and mass comparisons, not for relativistic effects near a real event horizon.
