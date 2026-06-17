"""
ZCBS Solar Simulator (LEDSS) — Session Logger  v1.0
Zero Carbon Building Systems Lab

Session logging + openBIS upload on END SESSION.
Place SUN_SQUARE.png, and config.yml next to this script.
Optional: pip install -r requirements.txt  (pybis, pyyaml)
Run: launch.vbs (silent) / run.bat / pythonw sun_logger.py
"""

import csv
import json
import os
import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

try:
    import yaml
except ImportError:
    yaml = None

try:
    from openbis_uploader import OpenBISUploader, list_data_files, setup_upload_logging
    OPENBIS_IMPORT_OK = OpenBISUploader.dependencies_available()
except ImportError:
    OpenBISUploader = None
    list_data_files = None
    setup_upload_logging = None
    OPENBIS_IMPORT_OK = False

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────
try:
    BASE = Path(__file__).resolve().parent
except NameError:
    BASE = Path.cwd()

LOG_CSV     = BASE / "sun_log.csv"
LEGACY_CSV  = BASE / "sun_sessions.csv"
STATS_JSON  = BASE / "sun_stats.json"
STATE_FILE  = BASE / "sun_state.json"
PREFS_FILE  = BASE / "app_prefs.json"
CONFIG_FILE = BASE / "config.yml"
IMG_FILE    = BASE / "SUN_SQUARE.png"
IMG_TARGET  = 340

LAB_MEMBERS = ["Loukas Mettas", "Dominique Maritz", "Marco Serra"]

OPENBIS_SPACES = [
    "SCHLUETER_LMETTAS",
    "SCHLUETER_DMARITZ",
    "SCHLUETER_GZORZETO",
    "SCHLUETER_HILLIAS",
    "SCHLUETER_JMCCARTY",
    "SCHLUETER_LGROBE",
    "SCHLUETER_SCARNO",
    "SCHLUETER_SERRAMA",
]

COLS = [
    "ID", "Date", "Start Time", "End Time", "Duration (h)",
    "Researcher", "Lab Member", "Operation", "Experiment",
    "Max Azimuth (deg)", "Min Azimuth (deg)",
    "Max Altitude (deg)", "Min Altitude (deg)",
    "WW Power (%)", "CW Power (%)", "IR Power (%)",
    "Remarks", "Maintenance Required",
    "OpenBIS Space", "OpenBIS Project", "OpenBIS Experiment", "OpenBIS User",
    "Upload Status", "Files Uploaded",
]

# Black / white UI — colour only on START and END buttons
C = {
    "outer":    "#888888",
    "frame":    "#000000",
    "bg":       "#ebebeb",
    "lf":       "#ebebeb",
    "entry":    "#ffffff",
    "entry_d":  "#d4d4d4",
    "text":     "#000000",
    "dim":      "#999999",
    "line":     "#bbbbbb",
    "green":    "#1D9E75",
    "red":      "#C0392B",
    "btn_txt":  "#ffffff",
}

F = "Chicago"
_IMG_SCALED = None


# ── Data layer ────────────────────────────────────────────────────────────────

def load_stats():
    if STATS_JSON.exists():
        try:
            d = json.loads(STATS_JSON.read_text(encoding="utf-8"))
            d.setdefault("total_hours", 0.0)
            d.setdefault("total_sessions", 0)
            return d
        except Exception:
            pass
    return {"total_hours": 0.0, "total_sessions": 0}


def save_stats(d):
    tmp = STATS_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    if STATS_JSON.exists():
        shutil.copy2(STATS_JSON, STATS_JSON.with_suffix(".bak"))
    os.replace(tmp, STATS_JSON)


def ensure_csv():
    if not LOG_CSV.exists():
        with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLS).writeheader()
        _migrate_legacy_csv()


def _migrate_legacy_csv():
    if not LEGACY_CSV.exists() or LOG_CSV.stat().st_size > len(",".join(COLS)) + 2:
        return
    try:
        with open(LEGACY_CSV, "r", newline="", encoding="utf-8") as f:
            legacy = list(csv.DictReader(f))
    except Exception:
        return
    if not legacy:
        return
    rows = []
    for i, r in enumerate(legacy, 1):
        rows.append({
            "ID": r.get("session_id", i),
            "Date": r.get("date", ""),
            "Start Time": r.get("start_time", ""),
            "End Time": r.get("end_time", ""),
            "Duration (h)": r.get("duration_hours", ""),
            "Researcher": r.get("researcher", ""),
            "Lab Member": r.get("lab_member", ""),
            "Operation": r.get("operation_mode", ""),
            "Experiment": r.get("experiment_name", ""),
            "Max Azimuth (deg)": "",
            "Min Azimuth (deg)": "",
            "Max Altitude (deg)": r.get("max_angle_deg", ""),
            "Min Altitude (deg)": "",
            "WW Power (%)": "",
            "CW Power (%)": "",
            "IR Power (%)": r.get("led_power_pct", ""),
            "Remarks": r.get("remarks", ""),
            "Maintenance Required": r.get("maintenance_required", ""),
            "OpenBIS Space": "",
            "OpenBIS Project": "",
            "OpenBIS Experiment": "",
            "OpenBIS User": "",
            "Upload Status": "",
            "Files Uploaded": "",
        })
    _write_csv_atomic(rows)
    total = 0.0
    for row in rows:
        try:
            total += float(row.get("Duration (h)", 0) or 0)
        except (TypeError, ValueError):
            pass
    save_stats({"total_hours": round(total, 4), "total_sessions": len(rows)})


def read_all_rows():
    ensure_csv()
    try:
        with open(LOG_CSV, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _write_csv_atomic(rows):
    tmp = LOG_CSV.with_suffix(".tmp")
    bak = LOG_CSV.with_suffix(".bak")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    if LOG_CSV.exists():
        shutil.copy2(LOG_CSV, bak)
    os.replace(tmp, LOG_CSV)


def append_row(row):
    rows = read_all_rows()
    rows.append({col: row.get(col, "") for col in COLS})
    _write_csv_atomic(rows)


def next_id():
    rows = read_all_rows()
    if not rows:
        return 1
    try:
        return int(rows[-1].get("ID", 0)) + 1
    except (ValueError, TypeError):
        return len(rows) + 1


def known_values(column):
    seen, out = set(), []
    for r in reversed(read_all_rows()):
        v = r.get(column, "").strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def clear_state():
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass


def load_config() -> dict:
    defaults = {
        "openbis": {
            "enabled": False,
            "url": "",
            "verify_ssl": True,
        },
        "upload": {
            "data_folder": "",
            "space": "",
            "dataset_type": "RAW_DATA",
            "file_extensions": [".csv", ".txt", ".tdms", ".lvm"],
            "move_after_upload": False,
            "uploaded_subfolder": "uploaded",
            "log_file": "openbis_upload.log",
        },
    }
    if yaml is None or not CONFIG_FILE.exists():
        return defaults
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        cfg = defaults.copy()
        cfg["openbis"].update(loaded.get("openbis", {}))
        cfg["upload"].update(loaded.get("upload", {}))
        cfg["openbis"].pop("username", None)
        cfg["openbis"].pop("password", None)
        return cfg
    except Exception:
        return defaults


def load_prefs() -> dict:
    if PREFS_FILE.exists():
        try:
            return json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_prefs(prefs: dict) -> None:
    PREFS_FILE.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


# ── Application ───────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("LEDSS Session Logger v1.0")
        self.resizable(False, False)
        self.configure(bg=C["outer"])

        self._running = False
        self._start_dt = None
        self._session_id = None
        self._tick_job = None
        self._fw = []
        self._pw = []
        self._pl = []
        self._obis_fw = []
        self._obis_uploader = None
        self._obis_logged_in = False
        self._obis_projects = []
        self._obis_experiments = []
        self._obis_selected_project = None
        self._obis_selected_experiment = None

        self.config = load_config()
        self.openbis_active = (
            bool(self.config.get("openbis", {}).get("enabled"))
            and OPENBIS_IMPORT_OK
            and OpenBISUploader is not None
        )
        if self.openbis_active and setup_upload_logging:
            setup_upload_logging(self.config["upload"].get("log_file", ""))

        self.prefs = load_prefs()
        self._init_ttk()
        ensure_csv()
        self._build()
        self._refresh()

        self.after(120, self._load_image)

        saved = load_state()
        if saved.get("active"):
            self.after(200, lambda: self._recover(saved))

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_ttk(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(
            "TCombobox",
            fieldbackground=C["entry"],
            background=C["entry"],
            foreground=C["text"],
            selectbackground="#333333",
            selectforeground="#ffffff",
            arrowcolor=C["text"],
            bordercolor="#888888",
            lightcolor="#888888",
            darkcolor="#888888",
            insertcolor=C["text"],
            padding=(4, 3),
        )
        st.map(
            "TCombobox",
            fieldbackground=[("readonly", C["entry"]), ("disabled", C["entry_d"])],
            foreground=[("disabled", C["dim"])],
            arrowcolor=[("disabled", C["dim"])],
        )

    def _load_image(self):
        global _IMG_SCALED
        if not IMG_FILE.exists():
            return
        try:
            raw = tk.PhotoImage(file=str(IMG_FILE))
            factor = max(1, raw.width() // IMG_TARGET)
            _IMG_SCALED = raw.subsample(factor, factor)
            self._img_lbl.configure(image=_IMG_SCALED, width=0, height=0)
            self._img_lbl.image = _IMG_SCALED
        except Exception:
            pass

    def _build(self):
        self.geometry("550x1400")

        shell = tk.Frame(self, bg=C["frame"], padx=1, pady=1)
        shell.pack(fill="both", expand=True, padx=5, pady=5)

        doc = tk.LabelFrame(
            shell,
            text="  ZCBS LEDSS Logger  ",
            font=(F, 10, "bold"),
            fg=C["text"],
            bg=C["bg"],
            relief="groove",
            borderwidth=3,
            labelanchor="n",
        )
        doc.pack(fill="both", expand=True, padx=1, pady=1)

        P = 10
        head = tk.Frame(doc, bg=C["bg"])
        head.pack(fill="x", padx=P, pady=(8, 2))

        img_row = tk.Frame(doc, bg=C["bg"])
        img_row.pack(fill="x", pady=(4, 6))
        self._img_lbl = tk.Label(img_row, bg=C["bg"], height=1)
        self._img_lbl.pack()

        tk.Frame(doc, bg=C["line"], height=1).pack(fill="x", padx=P)

        self._form_wrap = tk.Frame(doc, bg=C["bg"])
        self._active_wrap = tk.Frame(doc, bg=C["bg"])
        self._form_wrap.pack(fill="x", padx=P, pady=(6, 0))

        self._build_setup()
        self._build_openbis()
        self._build_params()

        self._start_btn = tk.Button(
            self._form_wrap,
            text="▶   START SESSION",
            font=(F, 11, "bold"),
            bg=C["green"],
            fg=C["btn_txt"],
            activebackground="#158C61",
            activeforeground=C["btn_txt"],
            relief="flat",
            pady=10,
            cursor="hand2",
            command=self._start,
        )
        self._start_btn.pack(fill="x", pady=(6, 0))

        self._build_active()

        tk.Frame(doc, bg=C["line"], height=1).pack(fill="x", padx=P, pady=(8, 0))

        self._hours_lf = self._lf(doc, "HOURS")
        self._hours_lf.pack(fill="x", padx=P, pady=(6, 0))
        self._hours_lf.columnconfigure(1, weight=1)
        self._hours_lf.columnconfigure(3, weight=1)

        self._hours_lbl = tk.Label(
            self._hours_lf, text="0.0 h", font=(F, 18, "bold"), fg=C["text"], bg=C["lf"]
        )
        self._hours_lbl.grid(row=0, column=0, sticky="w", padx=(6, 2), pady=4)
        tk.Label(
            self._hours_lf,
            text="machine hours",
            font=(F, 8),
            fg="#666666",
            bg=C["lf"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(0, 20))

        self._sess_lbl = tk.Label(
            self._hours_lf, text="0", font=(F, 18, "bold"), fg=C["text"], bg=C["lf"]
        )
        self._sess_lbl.grid(row=0, column=2, sticky="w", padx=(0, 2))
        tk.Label(
            self._hours_lf,
            text="sessions",
            font=(F, 8),
            fg="#666666",
            bg=C["lf"],
            anchor="w",
        ).grid(row=0, column=3, sticky="w", padx=(0, 6))

        self._recent_lf = self._lf(doc, "RECENT")
        self._recent_lf.pack(fill="x", padx=P, pady=(6, 0))

        foot = tk.Frame(doc, bg=C["bg"])
        foot.pack(fill="x", padx=P, pady=(6, 8))
        self._status_lbl = tk.Label(foot, text="ready", font=(F, 8), fg="#777777", bg=C["bg"])
        self._status_lbl.pack(side="left")
        tk.Button(
            foot,
            text="Export CSV",
            font=(F, 8),
            relief="groove",
            cursor="hand2",
            bg=C["bg"],
            fg=C["text"],
            command=self._export,
        ).pack(side="right")

    def _lf(self, parent, title):
        return tk.LabelFrame(
            parent,
            text=f"  {title}  ",
            font=(F, 8, "bold"),
            fg=C["text"],
            bg=C["lf"],
            relief="groove",
            borderwidth=2,
        )

    def _entry(self, parent, var, width=10, param=False):
        e = tk.Entry(
            parent,
            textvariable=var,
            font=(F, 9),
            bg=C["entry"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="solid",
            borderwidth=1,
            width=width,
        )
        (self._pw if param else self._fw).append(e)
        return e

    def _combo(self, parent, var, values, readonly=False):
        c = ttk.Combobox(
            parent,
            textvariable=var,
            font=(F, 9),
            state="readonly" if readonly else "normal",
        )
        c["values"] = values
        self._fw.append(c)
        return c

    def _lbl(self, parent, text, row, col, param=False, **kw):
        l = tk.Label(
            parent,
            text=text,
            font=(F, 9),
            fg=C["text"],
            bg=C["lf"],
            anchor="e",
            **kw,
        )
        l.grid(row=row, column=col, sticky="e", padx=(6 if col == 0 else 4, 2), pady=2)
        if param:
            self._pl.append(l)
        return l

    def _build_setup(self):
        lf = self._lf(self._form_wrap, "SETUP")
        lf.pack(fill="x", pady=(0, 6))
        lf.columnconfigure(1, weight=1)

        self.researcher_var = tk.StringVar()
        self._lbl(lf, "Researcher:", 0, 0)
        self.researcher_combo = self._combo(lf, self.researcher_var, known_values("Researcher"))
        self.researcher_combo.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=3)

        self.labmember_var = tk.StringVar()
        self._lbl(lf, "Lab member:", 1, 0)
        self.labmember_combo = self._combo(lf, self.labmember_var, LAB_MEMBERS, readonly=True)
        self.labmember_combo.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=3)

        self.exp_var = tk.StringVar()
        self._lbl(lf, "Experiment:", 2, 0)
        self.exp_combo = self._combo(lf, self.exp_var, known_values("Experiment"))
        self.exp_combo.grid(row=2, column=1, sticky="ew", padx=(0, 6), pady=3)

    def _build_openbis(self):
        up = self.config.get("upload", {})
        lf = self._lf(self._form_wrap, "OPENBIS / DATA")
        lf.pack(fill="x", pady=(0, 6))
        lf.columnconfigure(1, weight=1)

        default_folder = (
            self.prefs.get("data_folder")
            or up.get("data_folder", "")
        )
        self.data_folder_var = tk.StringVar(value=default_folder)

        tk.Label(
            lf,
            text="Data folder:",
            font=(F, 9),
            fg=C["text"],
            bg=C["lf"],
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=(6, 2), pady=3)

        folder_row = tk.Frame(lf, bg=C["lf"])
        folder_row.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=3)
        folder_row.columnconfigure(0, weight=1)

        self.data_folder_entry = tk.Entry(
            folder_row,
            textvariable=self.data_folder_var,
            font=(F, 9),
            bg=C["entry"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="solid",
            borderwidth=1,
        )
        self.data_folder_entry.grid(row=0, column=0, sticky="ew")
        self.data_folder_entry.bind("<FocusOut>", lambda _e: self._save_data_folder_pref())
        self._obis_fw.append(self.data_folder_entry)

        self._browse_btn = tk.Button(
            folder_row,
            text="Browse…",
            font=(F, 8),
            relief="groove",
            cursor="hand2",
            bg=C["lf"],
            fg=C["text"],
            command=self._browse_data_folder,
        )
        self._browse_btn.grid(row=0, column=1, padx=(4, 0))
        self._obis_fw.append(self._browse_btn)

        default_space = up.get("space", "")
        if default_space not in OPENBIS_SPACES:
            default_space = ""
        self.obis_space_var = tk.StringVar(value=default_space)
        self._lbl(lf, "Space:", 1, 0)
        self.obis_space_combo = ttk.Combobox(
            lf,
            textvariable=self.obis_space_var,
            values=OPENBIS_SPACES,
            font=(F, 9),
            state="readonly",
        )
        self.obis_space_combo.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.obis_space_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_obis_space_change())
        self._obis_fw.append(self.obis_space_combo)

        signin_row = tk.Frame(lf, bg=C["lf"])
        signin_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 4))
        self._obis_signin_btn = tk.Button(
            signin_row,
            text="Sign in to openBIS",
            font=(F, 9),
            relief="groove",
            cursor="hand2",
            bg=C["lf"],
            fg=C["text"],
            command=self._openbis_sign_in,
        )
        self._obis_signin_btn.pack(side="left")
        self._obis_fw.append(self._obis_signin_btn)

        self.obis_project_var = tk.StringVar()
        self._obis_project_lbl = self._lbl(lf, "Project:", 3, 0)
        self.obis_project_combo = ttk.Combobox(
            lf,
            textvariable=self.obis_project_var,
            font=(F, 9),
            state="disabled",
        )
        self.obis_project_combo.grid(row=3, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.obis_project_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_obis_project_selected()
        )
        self._obis_fw.append(self.obis_project_combo)

        self.obis_exp_var = tk.StringVar()
        self._obis_exp_lbl = self._lbl(lf, "OBIS experiment:", 4, 0)
        self.obis_exp_combo = ttk.Combobox(
            lf,
            textvariable=self.obis_exp_var,
            font=(F, 9),
            state="disabled",
        )
        self.obis_exp_combo.grid(row=4, column=1, sticky="ew", padx=(0, 6), pady=3)
        self.obis_exp_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_obis_experiment_selected()
        )
        self._obis_fw.append(self.obis_exp_combo)

        self._obis_exp_id_lbl = tk.Label(
            lf,
            text="Sign in, then choose project and experiment from openBIS.",
            font=(F, 8),
            fg="#666666",
            bg=C["lf"],
            anchor="w",
            wraplength=420,
            justify="left",
        )
        self._obis_exp_id_lbl.grid(row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 2))

        self.upload_var = tk.BooleanVar(value=self.openbis_active)
        self._upload_cb = tk.Checkbutton(
            lf,
            text="Upload to openBIS on end (sign in before starting)",
            variable=self.upload_var,
            font=(F, 9),
            fg=C["text"],
            bg=C["lf"],
            activebackground=C["lf"],
            selectcolor=C["entry"],
        )
        self._upload_cb.grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 4))

        self._obis_conn_lbl = tk.Label(
            lf,
            text="openBIS: not connected",
            font=(F, 8),
            fg="#888888",
            bg=C["lf"],
            anchor="w",
        )
        self._obis_conn_lbl.grid(row=7, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 2))

        if not self.openbis_active:
            self._obis_conn_lbl.grid_remove()
            note = "openBIS off — "
            if not self.config.get("openbis", {}).get("enabled"):
                note += "disabled in config.yml"
            elif not OPENBIS_IMPORT_OK:
                note += "run: pip install -r requirements.txt"
            else:
                note += "check config.yml"
            tk.Label(
                lf,
                text=note,
                font=(F, 8),
                fg="#888888",
                bg=C["lf"],
                anchor="w",
            ).grid(row=8, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))
            self.upload_var.set(False)
            self._upload_cb.config(state=tk.DISABLED)
            self._obis_signin_btn.config(state=tk.DISABLED)
            for w in self._obis_fw:
                try:
                    if isinstance(w, ttk.Combobox):
                        w.config(state="disabled")
                    else:
                        w.config(state=tk.DISABLED, bg=C["entry_d"])
                except Exception:
                    pass
        else:
            exts = ", ".join(up.get("file_extensions", []))
            n_files = len(list_data_files(self._get_data_folder(), up.get("file_extensions", [])))
            self._obis_file_count_lbl = tk.Label(
                lf,
                text=f"Ready files in folder: {n_files}  ·  types: {exts}",
                font=(F, 8),
                fg="#666666",
                bg=C["lf"],
                anchor="w",
            )
            self._obis_file_count_lbl.grid(row=8, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))
            self._set_obis_connection_status(False)

    def _openbis_log_path(self) -> Path:
        name = self.config.get("upload", {}).get("log_file", "openbis_upload.log")
        p = Path(name)
        return p if p.is_absolute() else BASE / p

    def _read_openbis_log_hint(self) -> str:
        log_path = self._openbis_log_path()
        if not log_path.exists():
            return ""
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return ""
        for line in reversed(lines[-20:]):
            if "ERROR" in line or "connection error" in line.lower():
                parts = line.split("  ")
                return parts[-1].strip() if parts else line.strip()
        for line in reversed(lines[-5:]):
            if "connected as" in line.lower():
                return line.strip().split("  ")[-1]
        return ""

    def _set_obis_connection_status(
        self, connected: bool, username: str = "", error: str = ""
    ):
        if not hasattr(self, "_obis_conn_lbl"):
            return
        if connected and username:
            self._obis_conn_lbl.config(
                text=f"openBIS: connected as {username}",
                fg="#1D6B42",
            )
        elif error:
            short = error if len(error) <= 72 else error[:69] + "…"
            self._obis_conn_lbl.config(
                text=f"openBIS: login failed — {short}",
                fg="#993C1D",
            )
        else:
            self._obis_conn_lbl.config(
                text="openBIS: not connected — sign in, then pick project and experiment",
                fg="#888888",
            )

    def _reset_openbis_selection(self, keep_login: bool = False):
        self._obis_projects = []
        self._obis_experiments = []
        self._obis_selected_project = None
        self._obis_selected_experiment = None
        self.obis_project_var.set("")
        self.obis_exp_var.set("")
        self.obis_project_combo.config(state="disabled", values=[])
        self.obis_exp_combo.config(state="disabled", values=[])
        if hasattr(self, "_obis_exp_id_lbl"):
            self._obis_exp_id_lbl.config(
                text="Sign in, then choose project and experiment from openBIS."
            )
        if not keep_login:
            self._obis_logged_in = False
            if self._obis_uploader:
                self._obis_uploader.disconnect()
                self._obis_uploader = None
            self._set_obis_connection_status(False)
            if hasattr(self, "_obis_signin_btn"):
                self._obis_signin_btn.config(text="Sign in to openBIS")

    def _on_obis_space_change(self):
        if self._obis_logged_in:
            self._reset_openbis_selection(keep_login=False)

    def _sync_obis_projects(self) -> bool:
        space = self.obis_space_var.get().strip()
        if not space or not self._obis_uploader:
            return False
        self._obis_projects = self._obis_uploader.list_projects(space)
        if not self._obis_projects:
            self._set_obis_connection_status(
                False,
                error=f"no projects in {space}",
            )
            self._set_status(f"openBIS: no projects in {space}")
            return False
        labels = [p["label"] for p in self._obis_projects]
        self.obis_project_combo.config(state="readonly", values=labels)
        self.obis_project_var.set("")
        self.obis_exp_combo.config(state="disabled", values=[])
        self.obis_exp_var.set("")
        self._obis_experiments = []
        self._obis_selected_project = None
        self._obis_selected_experiment = None
        self._obis_exp_id_lbl.config(
            text=f"Connected — choose a project ({len(self._obis_projects)} on server)."
        )
        return True

    def _on_obis_project_selected(self):
        label = self.obis_project_var.get().strip()
        project = next((p for p in self._obis_projects if p["label"] == label), None)
        if not project:
            for p in self._obis_projects:
                if p["code"] == label:
                    project = p
                    break
        if not project:
            return
        self._obis_selected_project = project
        space = self.obis_space_var.get().strip()
        self._obis_experiments = self._obis_uploader.list_experiments(
            space, project["code"]
        )
        self._obis_selected_experiment = None
        self.obis_exp_var.set("")
        if not self._obis_experiments:
            self.obis_exp_combo.config(state="disabled", values=[])
            self._obis_exp_id_lbl.config(
                text=f"No experiments in {project['path']} — create one on the openBIS website."
            )
            return
        labels = [e["label"] for e in self._obis_experiments]
        self.obis_exp_combo.config(state="readonly", values=labels)
        self._obis_exp_id_lbl.config(
            text=f"Choose an experiment ({len(self._obis_experiments)} in {project['code']})."
        )

    def _on_obis_experiment_selected(self):
        label = self.obis_exp_var.get().strip()
        experiment = next(
            (e for e in self._obis_experiments if e["label"] == label), None
        )
        if not experiment:
            for e in self._obis_experiments:
                if e["code"] == label or e["identifier"] == label:
                    experiment = e
                    break
        if not experiment:
            return
        self._obis_selected_experiment = experiment
        self._obis_exp_id_lbl.config(
            text=f"Identifier: {experiment['identifier']}"
        )
        user = self._obis_uploader.username if self._obis_uploader else ""
        if user and hasattr(self, "_obis_conn_lbl"):
            self._obis_conn_lbl.config(
                text=(
                    f"openBIS: {user}  →  {experiment['identifier']}"
                ),
                fg="#1D6B42",
            )
        self._set_status(f"openBIS target: {experiment['identifier']}")

    def _get_data_folder(self) -> Path:
        return Path(self.data_folder_var.get().strip())

    def _save_data_folder_pref(self):
        path = self.data_folder_var.get().strip()
        if path:
            self.prefs["data_folder"] = path
            save_prefs(self.prefs)
        self._refresh_obis_file_count()

    def _browse_data_folder(self):
        initial = self.data_folder_var.get().strip()
        chosen = filedialog.askdirectory(
            title="Select experiment data folder",
            initialdir=initial if initial and Path(initial).is_dir() else None,
            parent=self,
        )
        if chosen:
            self.data_folder_var.set(chosen.replace("\\", "/"))
            self._save_data_folder_pref()

    def _refresh_obis_file_count(self):
        if not self.openbis_active or not hasattr(self, "_obis_file_count_lbl"):
            return
        up = self.config.get("upload", {})
        folder = self._get_data_folder()
        exts = up.get("file_extensions", [])
        n = len(list_data_files(folder, exts)) if str(folder) else 0
        self._obis_file_count_lbl.config(
            text=f"Ready files in folder: {n}  ·  types: {', '.join(exts)}"
        )

    def _build_params(self):
        lf = self._lf(self._form_wrap, "PARAMETERS")
        lf.pack(fill="x", pady=(0, 6))
        lf.columnconfigure(1, weight=1)
        lf.columnconfigure(3, weight=1)

        tk.Label(
            lf,
            text="Operation:",
            font=(F, 9),
            fg=C["text"],
            bg=C["lf"],
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=(6, 2), pady=(4, 2))

        self.op_var = tk.StringVar(value="Restrictive")
        op_row = tk.Frame(lf, bg=C["lf"])
        op_row.grid(row=0, column=1, columnspan=3, sticky="w", padx=(0, 6), pady=(4, 2))
        for val in ("Restrictive", "Unrestrictive"):
            rb = tk.Radiobutton(
                op_row,
                text=val,
                variable=self.op_var,
                value=val,
                font=(F, 9),
                fg=C["text"],
                bg=C["lf"],
                activebackground=C["lf"],
                selectcolor=C["lf"],
                command=self._on_op_change,
            )
            rb.pack(side="left", padx=(0, 16))
            self._fw.append(rb)

        tk.Frame(lf, bg=C["line"], height=1).grid(
            row=1, column=0, columnspan=4, sticky="ew", padx=6, pady=(2, 4)
        )

        self.max_az_var = tk.StringVar()
        self.min_az_var = tk.StringVar()
        self._lbl(lf, "Max az (°):", 2, 0, param=True)
        self._entry(lf, self.max_az_var, param=True).grid(
            row=2, column=1, sticky="ew", padx=(0, 4), pady=2
        )
        self._lbl(lf, "Min az (°):", 2, 2, param=True)
        self._entry(lf, self.min_az_var, param=True).grid(
            row=2, column=3, sticky="ew", padx=(0, 6), pady=2
        )

        self.max_alt_var = tk.StringVar()
        self.min_alt_var = tk.StringVar()
        self._lbl(lf, "Max alt (°):", 3, 0, param=True)
        self._entry(lf, self.max_alt_var, param=True).grid(
            row=3, column=1, sticky="ew", padx=(0, 4), pady=2
        )
        self._lbl(lf, "Min alt (°):", 3, 2, param=True)
        self._entry(lf, self.min_alt_var, param=True).grid(
            row=3, column=3, sticky="ew", padx=(0, 6), pady=2
        )

        self.ww_var = tk.StringVar()
        self.cw_var = tk.StringVar()
        self.ir_var = tk.StringVar()
        prow_wrap = tk.Frame(lf, bg=C["lf"])
        prow_wrap.grid(row=4, column=0, columnspan=4, sticky="ew", padx=4, pady=(2, 6))
        prow = tk.Frame(prow_wrap, bg=C["lf"])
        prow.pack(anchor="center")
        for i, (lbl_txt, var) in enumerate(
            [("WW %:", self.ww_var), ("CW %:", self.cw_var), ("IR %:", self.ir_var)]
        ):
            pad_left = 14 if i > 0 else 0
            l = tk.Label(
                prow, text=lbl_txt, font=(F, 9), fg=C["text"], bg=C["lf"], anchor="e"
            )
            l.grid(row=0, column=i * 2, sticky="e", padx=(pad_left, 4), pady=2)
            self._pl.append(l)
            self._entry(prow, var, width=5, param=True).grid(
                row=0, column=i * 2 + 1, sticky="w", padx=(0, 0), pady=2
            )

    def _build_active(self):
        lf = self._lf(self._active_wrap, "IN PROGRESS")
        lf.pack(fill="x", pady=(0, 6))

        self._timer_lbl = tk.Label(
            lf, text="00:00:00", font=(F, 28, "bold"), fg=C["text"], bg=C["lf"]
        )
        self._timer_lbl.pack(pady=(6, 2))

        self._info_lbl = tk.Label(lf, text="", font=(F, 8), fg="#555555", bg=C["lf"])
        self._info_lbl.pack(pady=(0, 6))

        tk.Frame(lf, bg=C["line"], height=1).pack(fill="x", padx=8)

        rmk_row = tk.Frame(lf, bg=C["lf"])
        rmk_row.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(
            rmk_row,
            text="Remarks / issues:",
            font=(F, 8),
            fg=C["text"],
            bg=C["lf"],
            anchor="w",
        ).pack(anchor="w")
        self._remarks = tk.Text(
            rmk_row,
            height=3,
            font=(F, 9),
            bg=C["entry"],
            fg=C["text"],
            insertbackground=C["text"],
            relief="solid",
            borderwidth=1,
            wrap="word",
            padx=4,
            pady=4,
        )
        self._remarks.pack(fill="x", pady=(3, 0))

        self._maint_var = tk.BooleanVar()
        tk.Checkbutton(
            lf,
            text="Flag for maintenance",
            variable=self._maint_var,
            font=(F, 9),
            fg=C["text"],
            bg=C["lf"],
            activebackground=C["lf"],
            selectcolor=C["entry"],
        ).pack(anchor="w", padx=8, pady=(4, 6))

        self._end_btn = tk.Button(
            self._active_wrap,
            text="■   END SESSION",
            font=(F, 11, "bold"),
            bg=C["red"],
            fg=C["btn_txt"],
            activebackground="#A93226",
            activeforeground=C["btn_txt"],
            relief="flat",
            pady=10,
            cursor="hand2",
            command=self._end,
        )

    def _on_op_change(self):
        restr = self.op_var.get() == "Restrictive"
        state = "normal" if restr else "disabled"
        for e in self._pw:
            e.config(state=state, bg=C["entry"] if restr else C["entry_d"])
        for l in self._pl:
            l.config(fg=C["text"] if restr else C["dim"])

    def _validate(self):
        errs = []
        if not self.researcher_var.get().strip():
            errs.append("Researcher")
        if not self.labmember_var.get().strip():
            errs.append("Lab member")
        if not self.exp_var.get().strip():
            errs.append("Experiment")
        if self.op_var.get() == "Restrictive":
            for lbl, var in [
                ("Max azimuth", self.max_az_var),
                ("Min azimuth", self.min_az_var),
                ("Max altitude", self.max_alt_var),
                ("Min altitude", self.min_alt_var),
                ("WW power", self.ww_var),
                ("CW power", self.cw_var),
                ("IR power", self.ir_var),
            ]:
                if not var.get().strip():
                    errs.append(lbl)
        if self.openbis_active and self.upload_var.get():
            if not self.data_folder_var.get().strip():
                errs.append("Data folder")
            if not self.obis_space_var.get().strip():
                errs.append("OpenBIS space")
            if not self._obis_logged_in:
                errs.append("openBIS sign-in")
            elif not self._obis_selected_project:
                errs.append("OpenBIS project")
            elif not self._obis_selected_experiment:
                errs.append("OpenBIS experiment")
        return errs

    def _openbis_destination(self) -> dict:
        project = self._obis_selected_project or {}
        experiment = self._obis_selected_experiment or {}
        space = self.obis_space_var.get().strip()
        return {
            "space": space,
            "project": project.get("code", ""),
            "experiment": experiment.get("code", ""),
            "project_path": project.get("path", ""),
            "experiment_path": experiment.get("identifier", ""),
        }

    def _prompt_openbis_login(self, title="openBIS login") -> tuple | None:
        """Modal login — credentials stay in memory only, never saved."""
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=C["bg"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(
            dlg,
            text="Sign in to openBIS for this session.\nPassword is not stored.",
            font=(F, 9),
            fg=C["text"],
            bg=C["bg"],
            justify="left",
        ).pack(padx=16, pady=(14, 10), anchor="w")

        form = tk.Frame(dlg, bg=C["bg"])
        form.pack(padx=16, pady=(0, 8), fill="x")
        form.columnconfigure(1, weight=1)

        user_var = tk.StringVar()
        pass_var = tk.StringVar()
        tk.Label(form, text="Username:", font=(F, 9), bg=C["bg"], fg=C["text"]).grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=4
        )
        user_entry = tk.Entry(form, textvariable=user_var, font=(F, 9), width=28)
        user_entry.grid(row=0, column=1, sticky="ew", pady=4)

        tk.Label(form, text="Password:", font=(F, 9), bg=C["bg"], fg=C["text"]).grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=4
        )
        pass_entry = tk.Entry(
            form, textvariable=pass_var, font=(F, 9), width=28, show="•"
        )
        pass_entry.grid(row=1, column=1, sticky="ew", pady=4)

        result = {"creds": None}

        def submit(_event=None):
            u, p = user_var.get().strip(), pass_var.get()
            if not u or not p:
                messagebox.showwarning(
                    "Missing fields", "Enter username and password.", parent=dlg
                )
                return
            result["creds"] = (u, p)
            dlg.destroy()

        def cancel():
            dlg.destroy()

        btns = tk.Frame(dlg, bg=C["bg"])
        btns.pack(padx=16, pady=(4, 14), fill="x")
        tk.Button(
            btns, text="Cancel", font=(F, 9), relief="groove", command=cancel
        ).pack(side="right")
        tk.Button(
            btns,
            text="Sign in",
            font=(F, 9, "bold"),
            bg=C["green"],
            fg=C["btn_txt"],
            relief="flat",
            command=submit,
        ).pack(side="right", padx=(0, 8))

        pass_entry.bind("<Return>", submit)
        user_entry.focus_set()
        self.update_idletasks()
        dlg.geometry(f"+{self.winfo_rootx() + 40}+{self.winfo_rooty() + 80}")
        self.wait_window(dlg)
        return result["creds"]

    def _login_openbis_for_session(self) -> bool:
        creds = self._prompt_openbis_login()
        if not creds:
            self._set_obis_connection_status(False)
            return False
        username, password = creds
        self._obis_uploader = OpenBISUploader(self.config)
        self._set_status("connecting to openBIS…")
        self.update_idletasks()
        if not self._obis_uploader.connect(username, password):
            detail = self._obis_uploader.last_error or self._read_openbis_log_hint()
            self._set_obis_connection_status(False, error=detail or "connection failed")
            self._obis_uploader = None
            self._set_status("openBIS login failed — check username and password")
            return False
        self._set_obis_connection_status(True, username)
        self._obis_logged_in = True
        self._obis_signin_btn.config(text="Signed in — refresh")
        if not self._sync_obis_projects():
            self._reset_openbis_selection(keep_login=False)
            return False
        self._set_status(f"openBIS connected as {username}")
        return True

    def _openbis_sign_in(self) -> bool:
        if not self.obis_space_var.get().strip():
            messagebox.showwarning(
                "OpenBIS space",
                "Select your openBIS space before signing in.",
                parent=self,
            )
            return False
        if self._obis_logged_in and self._obis_uploader:
            self._reset_openbis_selection(keep_login=True)
            return self._sync_obis_projects()
        return self._login_openbis_for_session()

    def _ensure_openbis_ready(self) -> bool:
        if not self.upload_var.get():
            return True
        if not self._obis_logged_in or not self._obis_uploader:
            messagebox.showwarning(
                "openBIS sign-in",
                "Sign in to openBIS, then choose a project and experiment.",
                parent=self,
            )
            return False
        if not self._obis_selected_project:
            messagebox.showwarning(
                "OpenBIS project",
                "Sign in to openBIS and choose a project from the list.",
                parent=self,
            )
            return False
        if not self._obis_selected_experiment:
            messagebox.showwarning(
                "OpenBIS experiment",
                "Choose an experiment that already exists on openBIS.\n\n"
                "New experiments must be created on the openBIS website first.",
                parent=self,
            )
            return False
        return True

    def _run_openbis_upload(self) -> dict:
        up = self.config["upload"]
        folder = self._get_data_folder()
        exts = up.get("file_extensions", [])
        empty = {"status": "Skipped", "ok": 0, "error": 0, "files_ok": [], "files_error": []}

        if not folder.is_dir():
            empty["status"] = "Folder missing"
            return empty

        if not self._obis_uploader or not self._obis_uploader.ensure_connected():
            if not self._login_openbis_for_session():
                empty["status"] = "Login required"
                return empty

        self._set_status("uploading to openBIS…")
        self.update_idletasks()
        return self._obis_uploader.upload_session_files(
            folder,
            self._openbis_destination(),
            exts,
        )

    def _disconnect_openbis(self):
        self._reset_openbis_selection(keep_login=False)

    def _session_snapshot(self):
        restr = self.op_var.get() == "Restrictive"
        return {
            "active": True,
            "session_id": self._session_id,
            "start_iso": self._start_dt.isoformat(),
            "researcher": self.researcher_var.get().strip(),
            "lab_member": self.labmember_var.get().strip(),
            "experiment": self.exp_var.get().strip(),
            "operation": self.op_var.get(),
            "max_az": self.max_az_var.get().strip() if restr else "",
            "min_az": self.min_az_var.get().strip() if restr else "",
            "max_alt": self.max_alt_var.get().strip() if restr else "",
            "min_alt": self.min_alt_var.get().strip() if restr else "",
            "ww": self.ww_var.get().strip() if restr else "",
            "cw": self.cw_var.get().strip() if restr else "",
            "ir": self.ir_var.get().strip() if restr else "",
            "obis_space": self.obis_space_var.get().strip(),
            "obis_project": self._obis_selected_project.get("path", "") if self._obis_selected_project else "",
            "obis_experiment": (
                self._obis_selected_experiment.get("identifier", "")
                if self._obis_selected_experiment
                else ""
            ),
            "upload_enabled": self.upload_var.get(),
            "data_folder": self.data_folder_var.get().strip(),
        }

    def _start(self):
        errs = self._validate()
        if errs:
            messagebox.showwarning(
                "Missing fields",
                "Complete the following:\n\n" + "\n".join(f"  — {e}" for e in errs),
                parent=self,
            )
            return

        if self.openbis_active and self.upload_var.get():
            if not self._ensure_openbis_ready():
                return

        self._running = True
        self._start_dt = datetime.now()
        self._session_id = next_id()
        save_state(self._session_snapshot())

        self._info_lbl.config(
            text=(
                f"{self.researcher_var.get().strip()}  ·  "
                f"{self.exp_var.get().strip()}  ·  "
                f"{self.op_var.get()}"
                + (
                    f"  ·  openBIS: {self._obis_selected_experiment['identifier']}"
                    if self._obis_selected_experiment
                    else (
                        f"  ·  openBIS: {self._obis_uploader.username}"
                        if self._obis_uploader
                        else ""
                    )
                )
            )
        )
        self._remarks.delete("1.0", "end")
        self._maint_var.set(False)

        self._form_wrap.pack_forget()
        self._active_wrap.pack(fill="x", padx=10, before=self._hours_lf)
        self._end_btn.pack(fill="x", pady=(0, 6))
        self._toggle_form("disabled")

        self.title("● RUNNING  —  LEDSS Logger")
        self._tick()
        self._set_status(f"session #{self._session_id} running")

    def _end(self):
        if not self._running:
            return

        now = datetime.now()
        duration = (now - self._start_dt).total_seconds() / 3600.0
        remarks = self._remarks.get("1.0", "end-1c").strip()
        maint = "Yes" if self._maint_var.get() else "No"
        restr = self.op_var.get() == "Restrictive"

        dest = self._openbis_destination()
        upload_status = "Skipped"
        files_uploaded = "0"
        upload_results = None

        if self.openbis_active and self.upload_var.get():
            up = self.config["upload"]
            folder = self._get_data_folder()
            exts = up.get("file_extensions", [])
            folder_str = str(folder)

            if not messagebox.askyesno(
                "Data files ready?",
                "Are your result files already in the data folder?\n\n"
                f"  {folder_str}\n\n"
                "Yes — end session and upload to openBIS\n"
                "No — keep session running",
                parent=self,
            ):
                self._set_status("session still running — place files, then end again")
                return

            n_files = len(list_data_files(folder, exts)) if folder.is_dir() else 0

            if not folder.is_dir():
                if not messagebox.askyesno(
                    "Data folder missing",
                    f"The data folder does not exist:\n\n  {folder}\n\n"
                    "End session without uploading?",
                    parent=self,
                ):
                    return
                upload_status = "Folder missing"
            elif n_files == 0:
                if not messagebox.askyesno(
                    "No data files",
                    f"No matching files in:\n\n  {folder}\n\n"
                    f"Expected types: {', '.join(exts)}\n\n"
                    "Place your results there, or end without uploading.",
                    parent=self,
                ):
                    return
                upload_status = "No files"
            else:
                upload_results = self._run_openbis_upload()
                upload_status = upload_results.get("status", "Failed")
                files_uploaded = str(upload_results.get("ok", 0))
                if upload_status == "OK":
                    uploaded = upload_results.get("files_ok", [])
                    file_lines = "\n".join(f"  · {name}" for name in uploaded)
                    messagebox.showinfo(
                        "openBIS upload complete",
                        "Data uploaded successfully.\n\n"
                        f"Destination:\n  {dest.get('experiment_path', '')}\n\n"
                        f"Files ({len(uploaded)}):\n{file_lines}",
                        parent=self,
                    )
                elif upload_status == "Duplicate":
                    dupes = upload_results.get("duplicates", [])
                    detail = upload_results.get("error_detail", "")
                    messagebox.showerror(
                        "Duplicate file on openBIS",
                        "Upload blocked — these files already exist in the "
                        "selected experiment:\n\n"
                        + "\n".join(f"  · {name}" for name in dupes)
                        + "\n\nRename your local files or remove the existing "
                        "datasets on openBIS, then end the session again.\n\n"
                        + (detail if detail and not dupes else ""),
                        parent=self,
                    )
                    self._set_status("upload blocked — duplicate file name on openBIS")
                    return
                elif upload_status not in ("OK",):
                    err_detail = upload_results.get("files_error", [])
                    create_err = upload_results.get("error_detail", "")
                    extra = f"\n\nFailed: {', '.join(err_detail)}" if err_detail else ""
                    if create_err:
                        extra += f"\n\n{create_err}"
                    messagebox.showwarning(
                        "openBIS upload",
                        f"Upload status: {upload_status}{extra}",
                        parent=self,
                    )

        row = {
            "ID": self._session_id,
            "Date": self._start_dt.strftime("%Y-%m-%d"),
            "Start Time": self._start_dt.strftime("%H:%M:%S"),
            "End Time": now.strftime("%H:%M:%S"),
            "Duration (h)": f"{duration:.4f}",
            "Researcher": self.researcher_var.get().strip(),
            "Lab Member": self.labmember_var.get().strip(),
            "Operation": self.op_var.get(),
            "Experiment": self.exp_var.get().strip(),
            "Max Azimuth (deg)": self.max_az_var.get().strip() if restr else "",
            "Min Azimuth (deg)": self.min_az_var.get().strip() if restr else "",
            "Max Altitude (deg)": self.max_alt_var.get().strip() if restr else "",
            "Min Altitude (deg)": self.min_alt_var.get().strip() if restr else "",
            "WW Power (%)": self.ww_var.get().strip() if restr else "",
            "CW Power (%)": self.cw_var.get().strip() if restr else "",
            "IR Power (%)": self.ir_var.get().strip() if restr else "",
            "Remarks": remarks,
            "Maintenance Required": maint,
            "OpenBIS Space": dest["space"] if self.upload_var.get() else "",
            "OpenBIS Project": dest.get("project_path", "") if self.upload_var.get() else "",
            "OpenBIS Experiment": dest.get("experiment_path", "") if self.upload_var.get() else "",
            "OpenBIS User": (
                self._obis_uploader.username if self._obis_uploader and self.upload_var.get() else ""
            ),
            "Upload Status": upload_status,
            "Files Uploaded": files_uploaded,
        }

        try:
            append_row(row)
            stats = load_stats()
            stats["total_hours"] = round(stats["total_hours"] + duration, 4)
            stats["total_sessions"] += 1
            save_stats(stats)
            clear_state()
        except Exception as exc:
            messagebox.showerror(
                "Save error",
                f"Could not save session:\n\n{exc}\n\nBackup preserved.",
                parent=self,
            )
            return

        self._disconnect_openbis()

        self._running = False
        if self._tick_job:
            self.after_cancel(self._tick_job)
            self._tick_job = None

        self._end_btn.pack_forget()
        self._active_wrap.pack_forget()
        self._form_wrap.pack(fill="x", padx=10, before=self._hours_lf)
        self._toggle_form("normal")
        self._on_op_change()

        self.researcher_combo["values"] = known_values("Researcher")
        self.exp_combo["values"] = known_values("Experiment")
        self.title("LEDSS Session Logger v1.0")

        self._refresh()
        self._refresh_obis_file_count()
        mins = int(duration * 60)
        flag = "  [MAINT]" if maint == "Yes" else ""
        up_flag = f"  ·  openBIS: {upload_status}" if self.upload_var.get() else ""
        self._set_status(f"#{self._session_id} saved — {mins} min{flag}{up_flag}")

    def _tick(self):
        if self._running and self._start_dt:
            secs = int((datetime.now() - self._start_dt).total_seconds())
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            self._timer_lbl.config(text=f"{h:02d}:{m:02d}:{s:02d}")
        self._tick_job = self.after(1000, self._tick)

    def _toggle_form(self, state):
        for w in self._fw:
            try:
                w.config(state=state)
            except Exception:
                pass
        if state == "normal":
            try:
                self.labmember_combo.config(state="readonly")
            except Exception:
                pass
            if self.openbis_active:
                for w in self._obis_fw:
                    try:
                        if w is self.obis_project_combo or w is self.obis_exp_combo:
                            w.config(
                                state="readonly"
                                if (
                                    w is self.obis_project_combo
                                    and self._obis_logged_in
                                    and self._obis_projects
                                )
                                or (
                                    w is self.obis_exp_combo
                                    and self._obis_experiments
                                )
                                else "disabled"
                            )
                        elif isinstance(w, ttk.Combobox):
                            w.config(state="readonly")
                        else:
                            w.config(state=tk.NORMAL, bg=C["lf"])
                    except Exception:
                        try:
                            w.config(state=tk.NORMAL)
                        except Exception:
                            pass
                    if hasattr(w, "winfo_class") and w.winfo_class() == "Entry":
                        w.config(bg=C["entry"])
                self._upload_cb.config(state=tk.NORMAL)
                self._obis_signin_btn.config(state=tk.NORMAL)
        elif self.openbis_active:
            for w in self._obis_fw:
                try:
                    if isinstance(w, ttk.Combobox):
                        w.config(state="disabled")
                    else:
                        w.config(state=tk.DISABLED)
                except Exception:
                    pass
                if hasattr(w, "winfo_class") and w.winfo_class() == "Entry":
                    w.config(bg=C["entry_d"])
            self._upload_cb.config(state=tk.DISABLED)
            self._obis_signin_btn.config(state=tk.DISABLED)

    def _recover(self, state):
        try:
            start = datetime.fromisoformat(state["start_iso"])
        except Exception:
            clear_state()
            return

        ans = messagebox.askyesno(
            "Unfinished session",
            "The logger was closed during an active session:\n\n"
            f"  Started:     {start.strftime('%d %b %Y  %H:%M')}\n"
            f"  Researcher:  {state.get('researcher', '?')}\n"
            f"  Lab member:  {state.get('lab_member', '?')}\n"
            f"  Experiment:  {state.get('experiment', '?')}\n\n"
            "Resume this session?",
            parent=self,
        )
        if not ans:
            clear_state()
            return

        self.researcher_var.set(state.get("researcher", ""))
        self.labmember_var.set(state.get("lab_member", ""))
        self.exp_var.set(state.get("experiment", ""))
        self.op_var.set(state.get("operation", "Restrictive"))
        self.max_az_var.set(state.get("max_az", ""))
        self.min_az_var.set(state.get("min_az", ""))
        self.max_alt_var.set(state.get("max_alt", ""))
        self.min_alt_var.set(state.get("min_alt", ""))
        self.ww_var.set(state.get("ww", ""))
        self.cw_var.set(state.get("cw", ""))
        self.ir_var.set(state.get("ir", ""))
        self.obis_space_var.set(state.get("obis_space", ""))
        self.upload_var.set(state.get("upload_enabled", self.openbis_active))
        if state.get("data_folder"):
            self.data_folder_var.set(state.get("data_folder", ""))

        saved_project = state.get("obis_project", "")
        saved_experiment = state.get("obis_experiment", "")

        if self.openbis_active and state.get("upload_enabled"):
            if not self._login_openbis_for_session():
                clear_state()
                return
            if saved_project:
                for project in self._obis_projects:
                    if project["path"] == saved_project or project["code"] == saved_project:
                        self.obis_project_var.set(project["label"])
                        self._on_obis_project_selected()
                        break
            if saved_experiment and self._obis_experiments:
                for experiment in self._obis_experiments:
                    if experiment["identifier"] == saved_experiment:
                        self.obis_exp_var.set(experiment["label"])
                        self._on_obis_experiment_selected()
                        break
            if not self._obis_selected_experiment:
                self._disconnect_openbis()
                clear_state()
                return

        self._running = True
        self._start_dt = start
        self._session_id = state.get("session_id", next_id())
        self._on_op_change()

        self._info_lbl.config(
            text=(
                f"{state.get('researcher', '')}  ·  "
                f"{state.get('experiment', '')}  ·  "
                f"{state.get('operation', '')}  (recovered)"
            )
        )
        self._form_wrap.pack_forget()
        self._active_wrap.pack(fill="x", padx=10, before=self._hours_lf)
        self._end_btn.pack(fill="x", pady=(0, 6))
        self._toggle_form("disabled")
        self.title("● RUNNING  —  LEDSS Logger")
        self._tick()
        self._set_status(f"session #{self._session_id} recovered")

    def _refresh(self):
        stats = load_stats()
        self._hours_lbl.config(text=f"{stats['total_hours']:.1f} h")
        self._sess_lbl.config(text=str(stats["total_sessions"]))

        for w in self._recent_lf.winfo_children():
            w.destroy()

        rows = read_all_rows()[-4:][::-1]
        if not rows:
            tk.Label(
                self._recent_lf,
                text="no sessions recorded",
                font=(F, 8),
                fg="#888888",
                bg=C["lf"],
            ).pack(anchor="w", padx=8, pady=4)
            return

        for r in rows:
            op = r.get("Operation", "")
            short = "[R]" if op.startswith("R") else "[U]"
            maint = r.get("Maintenance Required", "") == "Yes"
            try:
                mins = f"{int(float(r.get('Duration (h)', 0) or 0) * 60)}m"
            except (ValueError, TypeError):
                mins = "?"
            txt = (
                f"#{r.get('ID', ''):>3}  {short}  "
                f"{r.get('Date', '')}  {mins:>4}"
                + ("  [!]" if maint else "")
            )
            name = r.get("Researcher", "")
            if name:
                txt += f"  {name}"
            tk.Label(
                self._recent_lf,
                text=txt,
                font=(F, 8),
                fg="#333333",
                bg=C["lf"],
                anchor="w",
            ).pack(fill="x", padx=8, pady=1)

    def _export(self):
        if not LOG_CSV.exists():
            messagebox.showinfo("No data", "No sessions logged yet.", parent=self)
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"ledss_{datetime.now():%Y%m%d_%H%M%S}.csv",
            parent=self,
        )
        if dest:
            shutil.copy2(LOG_CSV, dest)
            self._set_status(f"exported → {Path(dest).name}")

    def _set_status(self, msg):
        self._status_lbl.config(text=msg)

    def on_close(self):
        if self._running:
            if not messagebox.askyesno(
                "Session running",
                "A session is in progress.\n\n"
                "State is saved — you can resume by reopening the app.\n\n"
                "Close anyway?",
                parent=self,
            ):
                return
        if self._tick_job:
            self.after_cancel(self._tick_job)
        self._disconnect_openbis()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
