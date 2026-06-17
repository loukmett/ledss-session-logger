"""
ZCBS Solar Simulator (LEDSS) — Session Logger  v0.9
Zero Carbon Building Systems Lab

Place Nord.ttf and SUN_SQUARE.png next to this script.
Data files are created automatically in the same folder.
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
IMG_FILE    = BASE / "SUN_SQUARE.png"
FONT_FILE   = BASE / "Nord.ttf"
IMG_TARGET  = 340   # display width in pixels (window stays 476×650)

LAB_MEMBERS = ["Loukas Mettas", "Dominique Maritz", "Marco Serra"]

COLS = [
    "ID", "Date", "Start Time", "End Time", "Duration (h)",
    "Researcher", "Lab Member", "Operation", "Experiment",
    "Max Azimuth (deg)", "Min Azimuth (deg)",
    "Max Altitude (deg)", "Min Altitude (deg)",
    "WW Power (%)", "CW Power (%)", "IR Power (%)",
    "Remarks", "Maintenance Required",
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


# ── Application ───────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("LEDSS Session Logger")
        self.resizable(False, False)
        self.configure(bg=C["outer"])

        self._running = False
        self._start_dt = None
        self._session_id = None
        self._tick_job = None
        self._fw = []
        self._pw = []
        self._pl = []

        self._init_font()
        self._init_ttk()
        ensure_csv()
        self._build()
        self._refresh()

        self.after(120, self._load_image)

        saved = load_state()
        if saved.get("active"):
            self.after(200, lambda: self._recover(saved))

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_font(self):
        global F

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
        self.geometry("550x1200")

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
        prow = tk.Frame(lf, bg=C["lf"])
        prow.grid(row=4, column=0, columnspan=4, sticky="ew", padx=4, pady=(2, 4))
        for i, (lbl_txt, var) in enumerate(
            [("WW %:", self.ww_var), ("CW %:", self.cw_var), ("IR %:", self.ir_var)]
        ):
            l = tk.Label(
                prow, text=lbl_txt, font=(F, 9), fg=C["text"], bg=C["lf"], anchor="e", width=5
            )
            l.pack(side="left", padx=(4 if i > 0 else 6, 2))
            self._pl.append(l)
            self._entry(prow, var, width=6, param=True).pack(side="left")

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
        return errs

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

        self._running = True
        self._start_dt = datetime.now()
        self._session_id = next_id()
        save_state(self._session_snapshot())

        self._info_lbl.config(
            text=(
                f"{self.researcher_var.get().strip()}  ·  "
                f"{self.exp_var.get().strip()}  ·  "
                f"{self.op_var.get()}"
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
        self.title("LEDSS Session Logger")

        self._refresh()
        mins = int(duration * 60)
        flag = "  [MAINT]" if maint == "Yes" else ""
        self._set_status(f"#{self._session_id} saved — {mins} min{flag}")

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
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
