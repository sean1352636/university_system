# Program Launcher

A comprehensive GUI launcher for all Python programs in this directory.

## Quick Start

Run the launcher:
```bash
python3 program_launcher.py
```

Or make it executable:
```bash
chmod +x program_launcher.py
./program_launcher.py
```

## Features

### 🚀 Main Features
- **Categorized Programs**: All programs organized by type
- **One-Click Launch**: Launch any program with a single click
- **Expandable Categories**: Show/hide categories as needed
- **Scrollable Interface**: Easy navigation through all programs
- **Status Bar**: See what's launching in real-time

### 📁 Categories

1. **🎮 Standalone Games**
   - 2048
   - Hangman

2. **🎯 Game Projects** (33+ games)
   - Aeroblasters
   - Flappy Bird
   - Snake
   - Tetris
   - And many more...

3. **🛠️ Standalone Utilities**
   - Calculator
   - Countdown Timer
   - Network Tools
   - Username Finder

4. **📦 Python Utility Projects** (20+ utilities)
   - Chatbot GUI
   - File Explorer
   - Image Viewer
   - Note Taking Apps
   - And more...

5. **🎓 91 Mini Projects**
   - Convert IPython to PDF
   - Digital Clock
   - Weather Forecast
   - QR Code Generator
   - And 87 more...

6. **🍽️ Restaurant Management**
   - Complete restaurant management system

## Directory Structure

```
other/
├── program_launcher.py          # Main launcher (THIS FILE)
├── games/
│   ├── standalone-games/       # Individual game scripts
│   └── [game projects]/        # Full game projects
├── standalone-utilities/        # Individual utility scripts
├── python-utilities/           # Utility project folders
├── 91_Python_Mini_Projects-main/ # Collection of 91 mini projects
└── RestaurantManagementSystem-main/ # Restaurant management
```

## How It Works

### Auto-Detection
The launcher automatically:
- Scans all directories
- Finds Python files and projects
- Identifies entry points (`main.py`, `app.py`, etc.)
- Creates buttons for each program

### Launching Programs
When you click a program button:
1. The launcher finds the correct entry point
2. Sets the working directory to the program's folder
3. Launches it in a new process
4. Shows launch status in the status bar

### Program Entry Points
The launcher looks for entry points in this order:
1. `main.py`
2. `app.py`
3. `run.py`
4. `__main__.py`
5. First `.py` file found

## Requirements

- Python 3.6+
- Tkinter (usually included with Python)

## Troubleshooting

### Program Won't Launch
- Check if the program has dependencies
- Some programs may require additional packages
- Check terminal/console for error messages

### GUI Doesn't Appear
- Make sure Tkinter is installed: `python3 -m tkinter`
- On Linux, you may need: `sudo apt install python3-tk`

### Program Crashes Immediately
- The program may require setup (installing dependencies)
- Check the program's own README/documentation
- Some programs need specific Python versions

## Tips

1. **Expand/Collapse**: Click the ▼/▶ button to show/hide categories
2. **Scroll**: Use mouse wheel to scroll through all programs
3. **Status Bar**: Check bottom of window for launch status
4. **Close**: Click X or "Quit" to close launcher

## Customization

The launcher is highly customizable. Edit `program_launcher.py` to:
- Change color scheme (see `setup_style()`)
- Modify categories (see `load_programs()`)
- Adjust grid layout (change `max_cols` in load methods)
- Add custom entry points (edit `find_entry_point()`)

## Adding New Programs

Simply add your Python program to the appropriate directory:
- Single script games → `games/standalone-games/`
- Game projects → `games/`
- Single script utilities → `standalone-utilities/`
- Utility projects → `python-utilities/`

The launcher will automatically detect them on next launch!

## License

This launcher is provided as-is for organizing and launching the programs in this directory.

---

**Enjoy exploring all the programs! 🚀**
