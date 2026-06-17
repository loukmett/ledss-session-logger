# ZCBS Solar Simulator (LEDSS) — Session Logger v1.0

Standalone Windows app for session authorisation, machine-hours logging, and **openBIS upload when a session ends**.

![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

Repository: [github.com/loukmett/ledss-session-logger](https://github.com/loukmett/ledss-session-logger)

---

## Features

- Session log to `sun_log.csv` (researcher, parameters, duration, remarks)
- Optional **openBIS upload on END SESSION** (no background watcher)
- Sign in to openBIS per session — **password never saved**
- **Project and experiment chosen from the server** (created only on the openBIS website)
- Duplicate-file check before upload
- Confirmation that data files are in the folder before ending a session

---

## Requirements

- Windows 10 / 11
- Python 3.8+ with tkinter
- For openBIS upload:
  ```bat
  pip install -r requirements.txt
  ```
- Place **`SUN_SQUARE.png`** next to `sun_logger.py` (included in repo)

---

## First-time setup

1. Clone or copy this folder to the lab PC.
2. Install dependencies:
   ```bat
   pip install -r requirements.txt
   ```
3. Edit **`config.yml`**:
   - `openbis.url` — ETH research data hub URL
   - `openbis.enabled` — `true` / `false`
   - `upload.space` — default space code (optional)
   - `upload.data_folder` — optional first-time default path
   - `upload.file_extensions` — e.g. `.tdms`, `.csv`, `.lvm`, `.txt`
   - `upload.dataset_type` — e.g. `RAW_DATA`
4. Double-click **`launch.vbs`** (or **`run.bat`**).

User-specific paths are saved in **`app_prefs.json`** (local, not committed).

---

## Workflow

1. Fill **SETUP** and **PARAMETERS**.
2. In **OPENBIS / DATA**: set **data folder** and **Space**.
3. Click **Sign in to openBIS** → choose **Project** and **OBIS experiment** from synced lists.
4. **START SESSION** — simulator runs; timer counts.
5. Save experiment output files into the data folder.
6. **END SESSION**:
   - Confirm files are in the folder
   - Files upload to the selected openBIS experiment
   - Success or error dialog; session saved to CSV

Projects and experiments must exist on openBIS before use. The logger does not create them.

---

## Runtime files (local only)

| File | Purpose |
|------|---------|
| `sun_log.csv` | Session history |
| `sun_stats.json` | Total hours / session count |
| `sun_state.json` | Crash recovery (active session) |
| `app_prefs.json` | Remembered data folder |
| `openbis_upload.log` | openBIS connection/upload log |

These are listed in `.gitignore` and stay on the workstation.

---

## Project files

| File | Role |
|------|------|
| `sun_logger.py` | Main application |
| `openbis_uploader.py` | openBIS login, listing, upload |
| `config.yml` | Server URL and upload defaults |
| `launch.vbs` / `run.bat` | Silent launch via `pythonw` |
| `requirements.txt` | `pybis`, `pyyaml` |

---

## Contact

Loukas Mettas · Dominique Maritz · Marco Serra — ZCBS Lab, ETH Zurich
