"""Main window of the calcium analysis app (Tkinter).

Create or open a session, scan the data folder, edit each file's protocol,
then run the analysis, edit ROIs or open the viewer. The analysis, ROI editor
and viewer run as separate processes (the same scripts you can run from the
command line), so the window never freezes and matplotlib's own windows
cannot clash with Tk.

All form logic lives in ``model.py``; this file only draws widgets.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

from ..config import EXPERIMENT_TYPES
from ..dyes import DYES
from ..outputs import all_keys, applicable_keys, specs_for, wanted
from ..scan import scan_folder
from ..sessionstore import load_all_sessions, save_session, session_path
from ..workspace import (REPO_ROOT, ensure_workspace, get_workspace,
                         set_workspace)
from . import model

STRING_KEYS = ["name", "data_dir", "file_prefix", "dye", "experiment_type",
               "off_labels",
               "default_dc", "dose_unit", "dose_label", "dose_dc",
               "dose_exclude_files", "dose_exclude_dose", "truncate",
               "detrend_sec", "detrend_pct", "resp_dff", "resp_k",
               "min_area", "max_area"]
BOOL_KEYS = ["dose_log", "detrend"]

RUN_TEXT = "▶  Run analysis"
RUNNING_TEXT = "Running…"

PROTOCOL_HELP = ("One event per line:  time, label     (times are mm.ss: "
                 "5.30 = 5 min 30 s)\n"
                 "LIFU labels:  4.5V   100Hz@DC20   STOP        "
                 "Chemical labels:  ISO   Yoda1   Yoda1@10uM")


def open_in_file_manager(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif os.name == "nt":
        os.startfile(str(path))                     # noqa: S606 (Windows only)
    else:
        subprocess.Popen(["xdg-open", str(path)])


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._reported: set[str] = set()
        # Errors inside button callbacks are otherwise printed to a terminal
        # nobody sees (e.g. when started from the desktop icon) and the button
        # just seems to do nothing. Show them in the log and a dialog instead.
        root.report_callback_exception = self._report_callback_exception
        root.title("Calcium analysis")
        root.geometry("1100x760")
        root.minsize(900, 600)

        self.workspace = ensure_workspace(get_workspace())
        self.sessions: dict = {}
        self.session_names: list[str] = []
        self.file_ids: list[str] = []
        self.protocols: dict[str, str] = {}
        self._cur_fid: str | None = None
        self._job_queue: queue.Queue = queue.Queue()
        self._analysis_running = False

        self.vars: dict[str, tk.Variable] = {}
        for k in STRING_KEYS:
            self.vars[k] = tk.StringVar()
        for k in BOOL_KEYS:
            self.vars[k] = tk.BooleanVar()

        self.out_vars: dict[str, tk.BooleanVar] = {
            k: tk.BooleanVar(value=True) for k in sorted(all_keys())}

        self._build_ui()
        self._set_form(model.default_form())
        self._refresh_sessions()
        self.root.after(100, self._poll_jobs)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        top = ttk.Frame(self.root, padding=(8, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Workspace:").pack(side="left")
        self.ws_label = ttk.Label(top, text=str(self.workspace))
        self.ws_label.pack(side="left", padx=6)
        ttk.Button(top, text="Change…",
                   command=self._change_workspace).pack(side="left")

        panes = ttk.PanedWindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)

        # ---- left: session list
        left = ttk.Frame(panes, padding=(0, 0, 8, 0))
        panes.add(left, weight=1)
        ttk.Label(left, text="Sessions").pack(anchor="w")
        self.session_list = tk.Listbox(left, exportselection=False, width=24)
        self.session_list.pack(fill="both", expand=True, pady=4)
        self.session_list.bind("<<ListboxSelect>>", self._on_select_session)
        ttk.Button(left, text="New session",
                   command=self._new_session).pack(fill="x")

        # ---- right: tabs + actions
        right = ttk.Frame(panes)
        panes.add(right, weight=4)
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self._build_setup_tab()
        self._build_protocol_tab()
        self._build_results_tab()
        self._build_advanced_tab()

        # "Run analysis" is the main action: first, bigger and bold; the other
        # buttons are plain and sit after a divider.
        self._run_font = tkfont.nametofont("TkDefaultFont").copy()
        self._run_font.configure(weight="bold",
                                 size=int(self._run_font.cget("size")) + 1)
        ttk.Style(self.root).configure("Run.TButton", font=self._run_font,
                                       padding=(18, 6))

        actions = ttk.Frame(right, padding=(0, 6))
        actions.pack(fill="x")
        self.run_btn = ttk.Button(actions, text=RUN_TEXT, style="Run.TButton",
                                  command=self._run)
        self.run_btn.pack(side="left", padx=(0, 10))
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y",
                                                       padx=(0, 10))
        ttk.Button(actions, text="Save",
                   command=self._save).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Edit ROIs…",
                   command=self._edit_rois).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="View traces…",
                   command=self._view).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Open results folder",
                   command=self._open_results).pack(side="left")

        ttk.Label(self.root, text="Log").pack(anchor="w", padx=8)
        self.log = ScrolledText(self.root, height=10, state="disabled",
                                font=("Menlo" if sys.platform == "darwin"
                                      else "Consolas", 10))
        self.log.pack(fill="x", padx=8, pady=(0, 8))

    def _row(self, parent, r, label, widget):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w",
                                           padx=(0, 8), pady=3)
        widget.grid(row=r, column=1, sticky="we", pady=3)

    def _build_setup_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Setup")
        tab.columnconfigure(1, weight=1)
        v = self.vars

        self._row(tab, 0, "Session name",
                  ttk.Entry(tab, textvariable=v["name"]))

        folder = ttk.Frame(tab)
        folder.columnconfigure(0, weight=1)
        ttk.Entry(folder, textvariable=v["data_dir"]).grid(
            row=0, column=0, sticky="we")
        ttk.Button(folder, text="Browse…",
                   command=self._browse_data).grid(row=0, column=1, padx=4)
        ttk.Button(folder, text="Scan",
                   command=self._scan).grid(row=0, column=2)
        self._row(tab, 1, "Data folder", folder)

        self._row(tab, 2, "File name prefix",
                  ttk.Entry(tab, textvariable=v["file_prefix"]))
        ttk.Label(tab, foreground="gray",
                  text="Text before the file id in the file names, e.g. "
                       "'20260623_' for 20260623_1.tif. Usually filled in by "
                       "Scan; leave empty if files are just 1.tif, 2.tif…"
                  ).grid(row=3, column=1, sticky="w")

        self._row(tab, 4, "Dye", ttk.Combobox(
            tab, textvariable=v["dye"], values=list(DYES), state="readonly"))
        etype = ttk.Combobox(tab, textvariable=v["experiment_type"],
                             values=list(EXPERIMENT_TYPES), state="readonly")
        etype.bind("<<ComboboxSelected>>", lambda e: self._update_type_frames())
        self._row(tab, 5, "Experiment type", etype)

        # LIFU-only options
        self.lifu_frame = ttk.LabelFrame(tab, text="LIFU dose axis",
                                         padding=8)
        self.lifu_frame.columnconfigure(1, weight=1)
        self._row(self.lifu_frame, 0, "Dose unit",
                  ttk.Entry(self.lifu_frame, textvariable=v["dose_unit"]))
        self._row(self.lifu_frame, 1, "Axis label",
                  ttk.Entry(self.lifu_frame, textvariable=v["dose_label"]))
        self._row(self.lifu_frame, 2, "Pool at duty cycle (%)",
                  ttk.Entry(self.lifu_frame, textvariable=v["dose_dc"]))
        self._row(self.lifu_frame, 3, "Default duty cycle (%)",
                  ttk.Entry(self.lifu_frame, textvariable=v["default_dc"]))
        self._row(self.lifu_frame, 4, "",
                  ttk.Checkbutton(self.lifu_frame, text="Log dose axis",
                                  variable=v["dose_log"]))

        # chemical-only options
        self.chem_frame = ttk.LabelFrame(tab, text="Chemical conditions",
                                         padding=8)
        self.chem_frame.columnconfigure(1, weight=1)
        self._row(self.chem_frame, 0, "'Off' labels",
                  ttk.Entry(self.chem_frame, textvariable=v["off_labels"]))
        ttk.Label(self.chem_frame, foreground="gray",
                  text="Labels that end the previous epoch without being "
                       "analysed themselves (e.g. STOP, ISO if ISO is a "
                       "wash).").grid(row=1, column=0, columnspan=2,
                                      sticky="w")
        self.type_row = 6
        self._update_type_frames()

    def _update_type_frames(self):
        if hasattr(self, "results_frame"):
            self._rebuild_results()
        self.lifu_frame.grid_forget()
        self.chem_frame.grid_forget()
        frame = (self.lifu_frame if self.vars["experiment_type"].get() == "lifu"
                 else self.chem_frame)
        frame.grid(row=self.type_row, column=0, columnspan=2, sticky="we",
                   pady=(10, 0))

    def _build_protocol_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Protocol")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)

        ttk.Label(tab, text=PROTOCOL_HELP, foreground="gray",
                  justify="left").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))

        files = ttk.Frame(tab)
        files.grid(row=1, column=0, sticky="ns", padx=(0, 10))
        ttk.Label(files, text="Files").pack(anchor="w")
        self.file_list = tk.Listbox(files, exportselection=False, width=14)
        self.file_list.pack(fill="y", expand=True, pady=4)
        self.file_list.bind("<<ListboxSelect>>", self._on_select_file)
        self.new_fid = tk.StringVar()
        ttk.Entry(files, textvariable=self.new_fid, width=14).pack(fill="x")
        ttk.Button(files, text="Add file id",
                   command=self._add_file).pack(fill="x", pady=(2, 0))
        ttk.Button(files, text="Remove selected",
                   command=self._remove_file).pack(fill="x", pady=(2, 0))

        editor = ttk.Frame(tab)
        editor.grid(row=1, column=1, sticky="nsew")
        editor.rowconfigure(1, weight=1)
        editor.columnconfigure(0, weight=1)
        self.protocol_title = ttk.Label(editor, text="(no file selected)")
        self.protocol_title.grid(row=0, column=0, sticky="w")
        self.protocol_text = tk.Text(editor, height=12, wrap="none",
                                     font=("Menlo" if sys.platform == "darwin"
                                           else "Consolas", 11))
        self.protocol_text.grid(row=1, column=0, sticky="nsew", pady=4)
        ttk.Button(editor, text="Copy this protocol to all files",
                   command=self._copy_to_all).grid(row=2, column=0,
                                                   sticky="w")

    def _build_results_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Results")
        ttk.Label(tab, foreground="gray", justify="left",
                  text="Choose which figures and CSV files the analysis "
                       "produces. The list depends on the experiment type "
                       "(Setup tab)."
                  ).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(anchor="w", pady=(8, 4))
        ttk.Button(bar, text="Select all",
                   command=lambda: self._set_all_outputs(True)).pack(side="left")
        ttk.Button(bar, text="Clear",
                   command=lambda: self._set_all_outputs(False)).pack(
                       side="left", padx=6)
        self.results_frame = ttk.Frame(tab)
        self.results_frame.pack(fill="both", expand=True, pady=(4, 0))
        self._rebuild_results()

    def _rebuild_results(self):
        """Redraw the checkbox grid for the current experiment type."""
        for w in self.results_frame.winfo_children():
            w.destroy()
        frame = self.results_frame
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Figure (png)").grid(row=0, column=1, padx=10)
        ttk.Label(frame, text="Table (csv)").grid(row=0, column=2, padx=10)
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._results_font = bold                 # keep a reference

        r = 1
        group = None
        for spec in specs_for(self.vars["experiment_type"].get()):
            if spec.group != group:
                group = spec.group
                ttk.Label(frame, text=group, font=bold).grid(
                    row=r, column=0, sticky="w", pady=(10, 2))
                r += 1
            ttk.Label(frame, text=spec.label).grid(row=r, column=0,
                                                   sticky="w", padx=(16, 0))
            for col, fmt in ((1, "png"), (2, "csv")):
                if fmt in spec.formats:
                    ttk.Checkbutton(
                        frame, variable=self.out_vars[f"{spec.name}.{fmt}"]
                    ).grid(row=r, column=col)
                else:
                    ttk.Label(frame, text="–", foreground="gray").grid(
                        row=r, column=col)
            if spec.note:
                ttk.Label(frame, text=spec.note, foreground="gray").grid(
                    row=r, column=3, sticky="w", padx=10)
            r += 1

    def _set_all_outputs(self, on: bool):
        for key in applicable_keys(self.vars["experiment_type"].get()):
            self.out_vars[key].set(on)

    def _build_advanced_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Advanced")
        tab.columnconfigure(1, weight=1)
        v = self.vars
        rows = [
            ("Truncate (file: minutes, …)", ttk.Entry(tab, textvariable=v["truncate"])),
            ("Exclude files from dose-response", ttk.Entry(tab, textvariable=v["dose_exclude_files"])),
            ("Exclude doses", ttk.Entry(tab, textvariable=v["dose_exclude_dose"])),
            ("Detrend photobleaching", ttk.Checkbutton(tab, variable=v["detrend"])),
            ("Detrend window (s)", ttk.Entry(tab, textvariable=v["detrend_sec"])),
            ("Detrend percentile", ttk.Entry(tab, textvariable=v["detrend_pct"])),
            ("Responder min ΔF/F₀", ttk.Entry(tab, textvariable=v["resp_dff"])),
            ("Responder k (× baseline SD)", ttk.Entry(tab, textvariable=v["resp_k"])),
            ("Min cell area (px)", ttk.Entry(tab, textvariable=v["min_area"])),
            ("Max cell area (px)", ttk.Entry(tab, textvariable=v["max_area"])),
        ]
        for r, (label, widget) in enumerate(rows):
            self._row(tab, r, label, widget)
        ttk.Label(tab, foreground="gray", justify="left",
                  text="Truncate, e.g. '6: 27' crops file 6 at minute 27.\n"
                       "For Fura-2 the ratio mostly cancels photobleaching, "
                       "so you may want to untick 'Detrend'."
                  ).grid(row=len(rows), column=0, columnspan=2, sticky="w",
                         pady=(10, 0))

    # ------------------------------------------------------- form <-> widgets
    def _store_protocol(self):
        if self._cur_fid in self.file_ids:
            self.protocols[self._cur_fid] = self.protocol_text.get("1.0", "end-1c")

    def _collect_form(self) -> dict:
        self._store_protocol()
        form = {k: self.vars[k].get() for k in STRING_KEYS + BOOL_KEYS}
        form["file_ids"] = list(self.file_ids)
        form["protocols"] = dict(self.protocols)
        form["outputs"] = [k for k, v in self.out_vars.items() if v.get()]
        return form

    def _set_form(self, form: dict):
        for k in STRING_KEYS + BOOL_KEYS:
            self.vars[k].set(form[k])
        # Outputs that do not apply to this experiment type stay ticked, so
        # they are ticked if the user switches type.
        chosen = set(form["outputs"])
        applicable = applicable_keys(form["experiment_type"])
        for key, var in self.out_vars.items():
            var.set(key in chosen if key in applicable else True)
        self.file_ids = list(form["file_ids"])
        self.protocols = dict(form["protocols"])
        self._cur_fid = None
        self._refresh_file_list(select=self.file_ids[0] if self.file_ids else None)
        self._update_type_frames()

    def _refresh_file_list(self, select=None):
        self.file_list.delete(0, "end")
        for fid in self.file_ids:
            self.file_list.insert("end", fid)
        if select is not None and select in self.file_ids:
            i = self.file_ids.index(select)
            self.file_list.selection_set(i)
            self._show_file(select)
        else:
            self._cur_fid = None
            self.protocol_text.delete("1.0", "end")
            self.protocol_title.config(text="(no file selected)")

    def _show_file(self, fid):
        self._cur_fid = fid
        self.protocol_title.config(text=f"Protocol for file {fid}")
        self.protocol_text.delete("1.0", "end")
        self.protocol_text.insert("1.0", self.protocols.get(fid, ""))

    def _on_select_file(self, _evt=None):
        sel = self.file_list.curselection()
        if not sel:
            return
        self._store_protocol()
        self._show_file(self.file_ids[sel[0]])

    def _add_file(self):
        fid = self.new_fid.get().strip()
        if not fid:
            return
        if fid in self.file_ids:
            messagebox.showinfo("Add file", f"File '{fid}' is already listed.")
            return
        self._store_protocol()
        self.file_ids.append(fid)
        self.protocols[fid] = ""
        self.new_fid.set("")
        self._refresh_file_list(select=fid)

    def _remove_file(self):
        sel = self.file_list.curselection()
        if not sel:
            return
        self._store_protocol()
        fid = self.file_ids.pop(sel[0])
        self.protocols.pop(fid, None)
        self._refresh_file_list(
            select=self.file_ids[min(sel[0], len(self.file_ids) - 1)]
            if self.file_ids else None)

    def _copy_to_all(self):
        if self._cur_fid is None:
            return
        form = self._collect_form()
        model.copy_protocol_to_all(form, self._cur_fid)
        self.protocols = form["protocols"]
        self._log(f"copied the protocol of file {self._cur_fid} to all files")

    # ------------------------------------------------------------- sessions
    def _change_workspace(self):
        path = filedialog.askdirectory(title="Choose the workspace folder",
                                       initialdir=str(self.workspace))
        if not path:
            return
        self.workspace = ensure_workspace(set_workspace(path))
        self.ws_label.config(text=str(self.workspace))
        self._refresh_sessions()
        self._log(f"workspace: {self.workspace}")

    def _is_builtin(self, name: str) -> bool:
        return name in self.sessions and not session_path(
            name, self.workspace).exists()

    def _refresh_sessions(self, select=None):
        self.sessions, problems = load_all_sessions(self.workspace)
        for msg in problems:
            self._log(f"warning: {msg}")
        self.session_list.delete(0, "end")
        self.session_names = sorted(self.sessions)
        for name in self.session_names:
            tag = "  (built-in)" if self._is_builtin(name) else ""
            self.session_list.insert("end", name + tag)
        if select in self.session_names:
            i = self.session_names.index(select)
            self.session_list.selection_set(i)

    def _on_select_session(self, _evt=None):
        sel = self.session_list.curselection()
        if not sel:
            return
        self._set_form(model.form_from_config(self.sessions[self.session_names[sel[0]]]))

    def _new_session(self):
        self.session_list.selection_clear(0, "end")
        self._set_form(model.default_form())

    def _browse_data(self):
        start = self.vars["data_dir"].get() or str(Path.home())
        path = filedialog.askdirectory(title="Choose the data folder",
                                       initialdir=start)
        if path:
            self.vars["data_dir"].set(path)
            self._scan()

    def _scan(self):
        folder = self.vars["data_dir"].get().strip()
        if not folder:
            messagebox.showinfo("Scan", "Choose the data folder first "
                                        "(Browse…).")
            return
        self._log(f"scanning {folder} …")
        try:
            result = scan_folder(folder)
        except (NotADirectoryError, OSError) as e:
            messagebox.showerror("Scan", str(e))
            return
        form = self._collect_form()
        for msg in model.apply_scan(form, result):
            self._log(msg)
        self._set_form(form)

    def _build_or_complain(self):
        try:
            return model.build_config(self._collect_form(), self.workspace)
        except model.FormError as e:
            messagebox.showerror(
                "Please fix", "\n".join("• " + p for p in e.problems))
            return None

    def _save(self, quiet=False) -> str | None:
        """Save the form as a session; returns its name, or None on failure."""
        name = self.vars["name"].get().strip()
        if self._is_builtin(name):
            messagebox.showinfo(
                "Built-in session",
                f"'{name}' is a built-in session and cannot be overwritten.\n"
                f"Change the name to save a copy.")
            return None
        cfg = self._build_or_complain()
        if cfg is None:
            return None
        path = save_session(cfg, self.workspace)
        self._refresh_sessions(select=cfg.name)
        if not quiet:
            self._log(f"saved {path}")
            missing = model.missing_files(cfg)
            if missing:
                self._log(f"warning: {len(missing)} data file(s) not found, "
                          f"e.g. {missing[0]} (check the file name prefix)")
        return cfg.name

    # ----------------------------------------------------------------- jobs
    def _name_for_job(self) -> str | None:
        """Name of the session to run: save first unless it is built-in.

        Returns None (after telling the user) when the data files are missing.
        """
        name = self.vars["name"].get().strip()
        if not self._is_builtin(name):
            name = self._save(quiet=True)
            if name is None:
                return None
        cfg = self.sessions.get(name)
        missing = model.missing_files(cfg) if cfg else []
        if missing:
            shown = ", ".join(missing[:6]) + (" …" if len(missing) > 6 else "")
            messagebox.showerror(
                "Data files not found",
                f"{len(missing)} file(s) expected in\n{cfg.data_dir}\n"
                f"were not found:\n{shown}\n\n"
                f"Check the data folder and the 'File name prefix' in the "
                f"Setup tab.")
            return None
        return name

    def _selected_fid(self) -> str | None:
        if self._cur_fid is None:
            messagebox.showinfo("Choose a file",
                                "Select a file in the Protocol tab first.")
        return self._cur_fid

    def _start_job(self, label, script, *extra, analysis=False):
        env = os.environ.copy()
        env["CALCIUM_WORKSPACE"] = str(self.workspace)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        args = [sys.executable, str(REPO_ROOT / script), *extra]
        self._log(f"--- {label}")
        try:
            proc = subprocess.Popen(
                args, cwd=str(REPO_ROOT), env=env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
                encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            messagebox.showerror("Could not start", str(e))
            return
        if analysis:
            self._analysis_running = True
            self.run_btn.state(["disabled"])
            self.run_btn.config(text=RUNNING_TEXT)

        def reader():
            for line in proc.stdout:
                self._job_queue.put(("line", line.rstrip("\n")))
            code = proc.wait()
            self._job_queue.put(("done", (label, code, analysis)))

        threading.Thread(target=reader, daemon=True).start()

    def _poll_jobs(self):
        try:
            while True:
                kind, payload = self._job_queue.get_nowait()
                if kind == "line":
                    self._log(payload)
                else:
                    label, code, analysis = payload
                    outcome = ("finished" if code == 0
                               else "FAILED (exit code %s)" % code)
                    self._log(f"--- {label}: {outcome}")
                    if analysis:
                        self._analysis_running = False
                        self.run_btn.state(["!disabled"])
                        self.run_btn.config(text=RUN_TEXT)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_jobs)

    def _run(self):
        if self._analysis_running:
            return
        name = self._name_for_job()
        if name:
            self._start_job(f"analysis of {name}", "analyze.py", name,
                            analysis=True)

    def _edit_rois(self):
        fid = self._selected_fid()
        name = self._name_for_job() if fid else None
        if name:
            self._start_job(f"ROI editor: {name} file {fid}", "edit_rois.py",
                            name, fid)

    def _view(self):
        fid = self._selected_fid()
        name = self._name_for_job() if fid else None
        if not name:
            return
        cfg = self.sessions.get(name)
        if cfg is not None and not wanted(cfg, "traces.csv"):
            messagebox.showinfo(
                "View traces",
                "This session does not produce the per-cell traces CSV that "
                "the viewer reads.\n\nTick 'Per-cell traces' in the Results "
                "tab and run the analysis again.")
            return
        self._start_job(f"viewer: {name} file {fid}", "view.py", name, fid)

    def _open_results(self):
        name = self.vars["name"].get().strip()
        cfg = self.sessions.get(name)
        if cfg is None:
            messagebox.showinfo("Results", "Save the session and run it first.")
            return
        open_in_file_manager(Path(cfg.out_dir))

    # ------------------------------------------------------------------ log
    def _report_callback_exception(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        print(text, file=sys.stderr)
        self._log("ERROR (the app hit a bug; please send this text):\n" + text)
        key = f"{exc.__name__}: {val}"
        if key not in self._reported:             # one dialog per distinct error
            self._reported.add(key)
            try:
                messagebox.showerror(
                    "Unexpected error",
                    f"{key}\n\nThe details are in the log pane at the "
                    f"bottom of the window.")
            except Exception:
                pass

    def _log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main():
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
