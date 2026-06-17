# ZCBS Solar Simulator (LEDSS) — Session Logger v0.9

Standalone workstation application for the **Zero Carbon Building Systems Lab** solar simulator. It authorises sessions, records who used the machine, logs experiment parameters, tracks cumulative machine hours, and exports a CSV audit trail.

Built for a dedicated PC next to the LabVIEW-controlled LEDSS rig — simple, offline, no dependencies beyond Python.

![Python 3.7+](https://img.shields.io/badge/python-3.7%2B-blue)
![Dependencies](https://img.shields.io/badge/deps-stdlib%20only-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## What it does

Before a researcher uses the sun simulator, they fill in a short form:

| Field | Notes |
|-------|--------|
| **Researcher** | Type a name or pick from previous sessions |
| **Lab member** | Loukas Mettas, Dominique Maritz, or Marco Serra |
| **Experiment** | New or existing experiment name |
| **Operation** | **Restrictive** (limited movement/power) or **Unrestrictive** |

For **Restrictive** operation, these parameters are required:

- Max / min azimuth (°)
- Max / min altitude (°)
- WW, CW, IR power (%)

The researcher presses **START SESSION** when the experiment begins and **END SESSION** when finished. At the end they can add remarks and flag maintenance if something went wrong.

The app records start time, end time, duration, all form fields, and running totals of machine hours.

---

## Screenshots / UI

Minimal black-and-white layout inspired by old Mac utility apps — grooved borders, utilitarian typography, colour only on the start/end buttons. Uses the **Nord** font and the lab logo (`SUN_SQUARE.png`) when those files are present in the app folder.

Window size: **476 × 650 px**, vertical layout.

---

## Requirements

- **Windows 10 / 11** (tested on the lab workstation)
- **Python 3.7+** — [python.org](https://www.python.org/downloads/)
  - During install, tick **“Add Python to PATH”**
- **tkinter** — included with the standard Windows Python installer
- No `pip` packages required

### Assets (included in this repo)

| File | Purpose |
|------|---------|
| `Nord.ttf` | UI font |
| `SUN_SQUARE.png` | Logo shown below the title |

---

## How to run

### Recommended — no terminal window

Double-click **`launch.vbs`**

### Alternative

Double-click **`run.bat`** — also silent (`pythonw`, no console)

### Command line

```bat
pythonw sun_logger.py
```

Use `python sun_logger.py` only when debugging (shows a console).

---

## Data files

Created automatically next to `sun_logger.py` on first run. **Do not edit manually.**

| File | Purpose |
|------|---------|
| `sun_log.csv` | Full session log |
| `sun_log.bak` | Backup before every save |
| `sun_stats.json` | Total machine hours + session count |
| `sun_state.json` | Active session (removed on clean end) |

### Safe writes

The CSV is updated atomically: write to a temp file → backup existing file → rename. A crash mid-save cannot corrupt the log.

Legacy data in `sun_sessions.csv` (older format) is migrated automatically on first launch.

### Crash recovery

If the app closes during an active session, state is kept in `sun_state.json`. On the next launch you are offered the option to resume.

### Export

Click **Export CSV** in the footer to save a timestamped copy anywhere (e.g. for reports or archiving).

---

## CSV columns

```
ID, Date, Start Time, End Time, Duration (h),
Researcher, Lab Member, Operation, Experiment,
Max Azimuth (deg), Min Azimuth (deg),
Max Altitude (deg), Min Altitude (deg),
WW Power (%), CW Power (%), IR Power (%),
Remarks, Maintenance Required
```

Restrictive-only columns are left empty for Unrestrictive sessions.

---

## Project layout

```
sun-logger-v0.9/sun-logger/
├── sun_logger.py    # Application (Python + tkinter)
├── launch.vbs       # Silent launcher (recommended)
├── run.bat          # Silent launcher (fallback)
├── Nord.ttf         # Font
├── SUN_SQUARE.png   # Logo
├── README.md        # This file
└── README.txt       # Short quick-reference for the lab PC
```

---

## Deployment on the lab PC

1. Copy the whole `sun-logger` folder to the simulator workstation.
2. Install Python 3 if not already present.
3. Pin **`launch.vbs`** to the desktop or taskbar.
4. Keep the folder writable so CSV/stats files can be updated.
5. Back up `sun_log.csv` periodically (or use Export CSV).

---

## Development

Single-file app — all logic lives in `sun_logger.py`:

- **UI** — tkinter, classic Mac-style grooved frames
- **Persistence** — CSV log + JSON stats + JSON session state
- **Font loading** — `Nord.ttf` via Windows GDI (no broadcast; avoids hang on some systems)

To change lab members, edit `LAB_MEMBERS` near the top of `sun_logger.py`.

---

## Licence

Internal lab tool — **Zero Carbon Building Systems Lab**, ETH Zurich.  
Font and logo assets belong to their respective owners; check before redistributing outside the lab.

---

## Contact

Lab team: Loukas Mettas · Dominique Maritz · Marco Serra
