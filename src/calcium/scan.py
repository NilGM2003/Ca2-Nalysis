"""Look at a data folder and work out which dye it holds and which file ids.

``scan_folder`` only looks at file names (nothing is read), so it is instant
and works for the "new session" form: pick a folder, get a proposed dye and
list of file ids, then adjust.

Rules, driven by the ``DYES`` table in ``dyes.py``:

* ratiometric dyes (Fura-2): ``<id>_340.TIF`` + ``<id>_380.TIF`` make one file
  id ``<id>``; a file whose partner is missing is reported, not used;
* single-channel files (no channel suffix) belong to the first single-channel
  dye in ``DYES`` (Calbryte);
* case and ``.tif`` / ``.tiff`` do not matter; hidden files (``._foo.tif`` on
  macOS) are ignored;
* a folder holding more than one kind is resolved in favour of the larger
  group, with a warning listing what was left out.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .dyes import DYES, TIF_SUFFIXES


@dataclass
class ScanResult:
    folder: Path
    dye: str | None                      # None when no usable TIF files found
    file_ids: list[str]
    warnings: list[str] = field(default_factory=list)


def _natural_key(s: str):
    """Sort '2' before '10' (and '001' before '002')."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def scan_folder(folder) -> ScanResult:
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(f"{folder} is not a folder")

    warnings: list[str] = []

    # lower-cased stem -> original stem, for every visible TIF file
    stems: dict[str, str] = {}
    for p in sorted(folder.iterdir()):
        if not (p.is_file() and not p.name.startswith(".")
                and p.suffix.lower() in TIF_SUFFIXES):
            continue
        low = p.stem.lower()
        if low in stems:
            warnings.append(f"'{p.name}' has the same name as "
                            f"'{stems[low]}' apart from case/extension; ignored")
            continue
        stems[low] = p.stem

    claimed: set[str] = set()            # stems that belong to a channel dye
    candidates: dict[str, list[str]] = {}

    for name, dye in DYES.items():
        if not dye.channels:
            continue
        chans = [c.lower() for c in dye.channels]
        groups: dict[str, dict] = {}
        for low, stem in stems.items():
            for c in chans:
                suffix = "_" + c
                if low.endswith(suffix) and len(low) > len(suffix):
                    g = groups.setdefault(
                        low[:-len(suffix)],
                        {"id": stem[:-len(suffix)], "have": set()})
                    g["have"].add(c)
                    claimed.add(low)
        ids = []
        for g in groups.values():
            if g["have"] == set(chans):
                ids.append(g["id"])
            else:
                lacking = [c for c in dye.channels if c.lower() not in g["have"]]
                warnings.append(f"'{g['id']}': no {', '.join(lacking)} file "
                                f"for {dye.name}; skipped")
        if ids:
            candidates[name] = ids

    single = [n for n, d in DYES.items() if not d.channels]
    plain = [stem for low, stem in stems.items() if low not in claimed]
    if plain and single:
        candidates[single[0]] = plain

    if not candidates:
        warnings.append(f"no usable TIF files found in {folder}")
        return ScanResult(folder, None, [], warnings)

    order = list(DYES)
    ranked = sorted(candidates.items(),
                    key=lambda kv: (-len(kv[1]), order.index(kv[0])))
    dye, ids = ranked[0]
    for other, other_ids in ranked[1:]:
        left_out = ", ".join(sorted(other_ids, key=_natural_key))
        warnings.append(f"folder also holds {other} recordings ({left_out}); "
                        f"they are left out because {dye} has more files")

    return ScanResult(folder, dye, sorted(ids, key=_natural_key), warnings)
