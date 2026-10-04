# Cell-stimulation calcium imaging

Analysis of calcium-imaging experiments on cultured cells, stimulated either
with LIFUS (low-intensity focused ultrasound) or with chemicals (e.g. Yoda1).
Single-channel dyes (Calbryte) and ratiometric dyes (Fura-2, 340/380) are
supported; each session declares its dye and experiment type.

## Layout

```
app.py                desktop app: sessions, protocols, run, ROI editor, viewer
Setup Mac.command     double-click: one-time setup on a new Mac (see "The app")
analyze.py            CLI entry point:  python analyze.py [session]
view.py               interactive frame + trace viewer
edit_rois.py          interactive manual ROI editor
src/calcium/          analysis package (session-agnostic)
  config.py             SessionConfig: everything one session needs
  workspace.py          workspace folder (sessions/, rois/, results/)
  sessionstore.py       JSON sessions + the built-in sessions/*.py ones
  scan.py               detect dye and file ids from a data folder
  gui/                  the app window (model.py = form logic, main_window.py)
  dyes.py               dye specs (which TIF files to load) + recording loader
  io.py                 load TIF stacks + per-frame timing (AQUACOSMOS tag)
  protocol.py           parse acquisition protocol into stimulation epochs
  segmentation.py       Otsu cell ROIs (+ manual-mask loader) + per-ROI traces
  roieditor.py          interactive manual ROI correction
  dff.py                dF/F0 with rolling-percentile photobleach detrending
  metrics.py            per-epoch whole-field + per-cell responder metrics
  viewer.py             interactive viewer behind view.py
  doseresponse.py       pooled and file-as-replicate aggregation (LIFUS)
  export.py             per-cell trace CSV export
  plotting.py           all figures
  pipeline.py           orchestration: run_session(config)
sessions/             dataset-specific configs (protocol, dye, exclusions, knobs)
  s20260609.py
scripts/              utilities: tif_to_mp4.py, setup_mac.sh, make_mac_app.sh, make_icon.py
tests/                unit tests (python -m unittest discover -s tests)
20260609/             raw data (TIF stacks + protocol xlsx)
Calci/                raw data of chemical / Fura-2 sessions
rois/                 hand-corrected ROI masks (<session>_<file>.npy)
results/<session>/    generated figures + CSVs
```

Raw data can live anywhere: each session's `data_dir` points to it.

## The app

```bash
uv run python app.py
```

One window to create a session (pick the data folder, **Scan** detects the dye
and file ids), type each file's protocol, then **Run analysis**, **Edit ROIs…**,
**View traces…** or open the results folder. The analysis, ROI editor and
viewer run as separate processes; their output appears in the log pane.

Sessions made in the app are saved as JSON in the **workspace folder**
(default `~/CalciumAnalysis`, changeable in the window): `sessions/`, `rois/`
and `results/` live there. The older `sessions/sYYYYMMDD.py` sessions are
listed as "(built-in)", keep their own paths, and can be run but not
overwritten (save under a new name for a copy). The command-line scripts see
both kinds.

### Desktop icon (macOS)

```bash
bash scripts/make_mac_app.sh          # creates "Calcium Analysis.app" on the Desktop
```

Double-click it to open the window. It is a thin launcher that runs
`uv run python app.py` in this repo, so it always uses the current code; run
the script again if you move or re-clone the repo, and once per computer. If
it does not open, check `~/Library/Logs/CalciumAnalysis.log`. The first launch
after a fresh checkout can take a minute while `uv` builds the environment.
The window appears in the Dock as "Python" (a limitation of script launchers).

### Installing on another Mac (no Python, no code editor)

1. Get the project folder: download it as a ZIP and unzip it (or `git clone`).
2. Double-click **`Setup Mac.command`** in that folder. The first time macOS may
   refuse; then right-click it, choose **Open**, and confirm.
3. Wait while it installs `uv`, builds the environment (this downloads Python
   and the libraries, a few minutes) and creates **Calcium Analysis** on the
   Desktop. It needs internet only for this step.
4. Open **Calcium Analysis** from the Desktop. macOS may ask to allow access
   to folders (Desktop, Documents); click Allow.

Everything is installed inside the project folder and the user's home folder;
no admin rights are needed. Setup can be run again at any time. After an update
of the code just replace the files (or `git pull`); run the setup again only if
`uv.lock` changed. If something fails, the messages in the setup window and
`~/Library/Logs/CalciumAnalysis.log` say what. Raw data is not part of the
project: each person points sessions at their own data folders. The built-in
sessions in `sessions/` refer to the original experiments' data folders and
will show as missing on other computers; new sessions are created in the app.

## Usage

```bash
uv run python analyze.py 20260609     # or: .venv/bin/python analyze.py 20260609
```

Per session this writes to `results/<session>/`.

Always (both experiment types):

- `{file}_dff.png` — whole-field ΔF/F₀ trace, epochs shaded
- `{file}_cells.png` — ROI overlay + per-cell ΔF/F₀ heatmap
- `{file}_celltraces.png` — all per-cell traces + across-cell mean
- `{file}_traces.csv` — per-cell traces
- `calcium_metrics.csv` — per-epoch metrics table

LIFUS sessions (`experiment_type="lifu"`):

- `dose_response_pooled[_noFx].png/.csv` — single cells pooled across files
- `dose_response_byfile[_noFx].png/.csv` — file-as-replicate dose-response
- `response_recruitment_by_dc[_noFx].png/.csv` — response and recruitment vs
  dose per duty cycle (only when the session sweeps more than one duty cycle)
- `latency[_noFx].png/.csv`, `latency_byfile[_noFx].png/.csv` — responder
  onset / time-to-peak from stimulation onset

Chemical sessions (`experiment_type="chemical"`):

- `condition_summary.csv` — one row per condition label (e.g. ISO, Yoda1):
  epoch metrics averaged across all epochs and files with that label, plus
  total cells and responders. The dose-response, duty-cycle and latency
  outputs above are LIFUS-only.

For ratiometric dyes (Fura-2) the "ΔF/F₀" traces are ΔR/R₀, with
R = F340 / F380.

## Experiment types and dyes

Two settings in the session config decide how a session is analysed.

**`experiment_type`** (default `"lifu"`):

- `"lifu"` — protocol labels carry a numeric dose (volts, PRF in Hz, …) and a
  duty cycle; the dose-response outputs are produced.
- `"chemical"` — protocol labels are condition names (`"Yoda1"`, `"ISO"`);
  a per-condition summary is produced instead.

**`dye`** (default `"calbryte"`) decides which TIF file(s) are loaded for each
file id:

| dye          | files loaded for id `001`              | signal                   |
|--------------|----------------------------------------|--------------------------|
| `"calbryte"` | `001.TIF`                              | F / F₀                   |
| `"fura2"`    | `001_340.TIF` and `001_380.TIF`        | R = F340 / F380, ΔR / R₀ |

For Fura-2 the file id is the shared prefix (`"001"`, not `"001_340"`); the
loader adds `_340` / `_380` itself and stops with a clear error if either file
is missing or the two stacks differ in shape. Cells are segmented on the F380
stack, and each ROI trace is the ratio of the ROI's mean F340 to its mean
F380. The whole-field trace is the ratio of the channel means. Another dye
needs one line in `DYES` in `dyes.py`.

File extensions are upper case (`.TIF`).

## Correcting the segmentation manually

The automatic Otsu segmentation often misses or merges cells. To fix a file by
hand:

```bash
uv run python edit_rois.py 20260612 4      # session, file id
uv run python edit_rois.py 20261001 001    # Fura-2: id without _340/_380
```

The editor opens on the projection image seeded with the current ROIs (for
Fura-2, the F380 projection, the same image used for segmentation). Pick a
tool (buttons or keys) and edit:

- **Add** (`a`) — draw a freehand loop to create a new ROI.
- **Delete** (`d`) — click an ROI to remove it.
- **Merge** (`m`) — click two ROIs to combine them.
- **Split** (`s`) — loop over part of an ROI to break it off.
- **Reshape** (`r`) — loop over an ROI to redraw its outline.
- **Undo** (`z`), **Reset** (back to auto), **BG** (mean / max / std-dev
  background), **Save**.

Save writes `rois/<session>_<file>.npy` in the repo root. Both `analyze.py`
and `view.py` load that mask automatically (verbatim, no area filter), so
**re-run `analyze.py <session>`** afterwards to regenerate traces and figures.
Delete the `.npy` to fall back to automatic segmentation.

## Adding a session

Create `sessions/sYYYYMMDD.py` defining a `CONFIG = SessionConfig(...)`
(data dir, file ids, protocol, dye, experiment type, and optional truncation /
dose-response exclusions), then register it in `sessions/__init__.py`
(import it **and** add it to `SESSIONS`).

Every file id in `file_ids` needs a key of the same name in `PROTOCOL`;
the config checks this when it loads. Protocols can differ per file.

A protocol is a list of `(minute, label)` events per file id. `"mm.ss"` times
are accepted (`18.30` = 18 min 30 s). An epoch runs from each entry to the
next event (an off label, the next entry, or the end of the recording).
Labels in `off_labels` (default `{"STOP"}`) end the previous epoch without
starting one of their own; the baseline is everything before the first epoch.

### Chemical session (Fura-2)

```python
PROTOCOL = {
    "001": [(2, "ISO"), (4, "Yoda1"), (6, "ISO")],
    "002": [(2, "ISO"), (4, "Yoda1"), (6, "ISO")],
}

CONFIG = SessionConfig(
    name="20261001",
    data_dir=ROOT / "Calci" / "Hek Experiments",
    out_dir=ROOT / "results" / "20261001",
    file_ids=["001", "002"],
    protocol=PROTOCOL,
    dye="fura2",
    experiment_type="chemical",
    # off_labels={"STOP", "ISO"},   # if ISO is a wash/bath, not an epoch
    # detrend=False,                # the ratio mostly cancels photobleaching
)
```

A label starting with a name is a condition; an optional number after the name
(`"Yoda1@10uM"`) is stored as its dose, otherwise the dose is NaN.

### LIFUS session

The **dose axis** is generic: a protocol label's leading number is the dose,
whatever its unit. Set `dose_unit`, `dose_label`, and `dose_log` to describe it
— e.g. a voltage ramp uses `"4.5V"` labels with `dose_unit="V"`; the PRF×DC
matrix in `s20260612.py` uses `"100Hz@DC20"` labels with `dose_unit="Hz"`,
`dose_label="PRF (Hz)"`, `dose_log=True`. An optional `@DC` suffix overrides
the duty cycle (`default_dc`, 40 % unless set). `dose_dc` selects which duty
cycle the pooled dose-response figures aggregate; all files always appear in
the per-file figures and `calcium_metrics.csv`. The `dose_*` settings only
matter for `experiment_type="lifu"`.
