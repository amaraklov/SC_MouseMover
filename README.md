# SC_MouseMover

Move the mouse for certain amounts and intervals to avoid SC going to sleep.

<img width="916" height="663" alt="image" src="https://github.com/user-attachments/assets/4e0bf809-0826-4ab6-9227-053afa54446e" />

## Features

- Mouse drift loop with configurable:  
  - Max movement distance [DIST[ (0-255 px)
  - Moves before return to original position
  - Smooth steps (How smooth the movement is)
  - Move Sec, how long between each move, in seconds
- Key loop with configurable key interval (between key presses 0-4.5 sec)
- Interactive SVG HUD with draggable bar controls
- F11 hotkey for key loop toggle
- F12 hotkey for mouse drift toggle
- In-app notices panel for state changes and events

## Requirements

- Windows
- Python 3.10+ recommended

## Install

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

## Run (source)

```powershell
python MouseMover.py
```

## Build EXE

This project includes a PyInstaller spec:

```powershell
pyinstaller .\MouseDriftHUD.spec
```

Build output:

- dist/MouseDriftHUD/MouseDriftHUD.exe

## Controls

- F11: Toggle key loop
- F12: Toggle mouse drift

## Project Structure

- MouseMover.py: Backend engine, hotkeys, API bridge, app window
- ui/svg_control_panel_restored.html: Main HUD/UI layout and interaction logic
- MouseDriftHUD.spec: PyInstaller build config
- requirements.txt: Python dependencies

## Notes

- You only have to download the Exe from the root folder, but I've included the entire source, so you can look through it and make sure it's safe, as virus sofware ay identify it as a key injection hack, it's not it's just moving the mouse, and itting [ if activated to accept missions.
- If hotkeys do not respond, run with adequate desktop/input permissions.
