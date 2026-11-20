"""Reproducibility check used in CI: regenerated outputs must equal the committed ones.

    python -m flood_it.drift            # compares working tree vs HEAD

Text-level `git diff` is too strict across OS / BLAS builds (last-digit float noise), so CSVs
and metrics.json are compared numerically (rtol 1e-6) and exactly for non-numeric fields.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys

import numpy as np
import pandas as pd

from .config import ROOT

RTOL, ATOL = 1e-6, 1e-9
PATTERNS = ["data/*.csv", "results/metrics.json", "results/validation_checks.csv", "powerbi/data/*.csv"]
SKIP = {"data/query_cost_log.csv"}


def _committed(path: str) -> str | None:
    r = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def _cmp_json(a, b, where="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = [f"{where}: keys differ {sorted(set(a) ^ set(b))}"] if set(a) != set(b) else []
        for k in set(a) & set(b):
            out += _cmp_json(a[k], b[k], f"{where}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{where}: list length {len(a)} vs {len(b)}"]
        return [e for x, y, i in zip(a, b, range(len(a))) for e in _cmp_json(x, y, f"{where}[{i}]")]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return [] if np.isclose(a, b, rtol=RTOL, atol=ATOL) else [f"{where}: {a} vs {b}"]
    return [] if a == b else [f"{where}: {a!r} vs {b!r}"]


def _cmp_csv(new: pd.DataFrame, old: pd.DataFrame, path: str) -> list[str]:
    if list(new.columns) != list(old.columns) or len(new) != len(old):
        return [f"{path}: shape/columns differ"]
    errs = []
    for c in new.columns:
        a, b = new[c], old[c]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            ok = np.isclose(a.astype(float), b.astype(float), rtol=RTOL, atol=ATOL, equal_nan=True)
        else:
            ok = (a.astype(object).fillna("").astype(str) == b.astype(object).fillna("").astype(str)).values
        if not ok.all():
            errs.append(f"{path}:{c} differs in {int((~ok).sum())} rows")
    return errs


def main() -> int:
    errors, n = [], 0
    for pat in PATTERNS:
        for p in sorted(ROOT.glob(pat)):
            rel = p.relative_to(ROOT).as_posix()
            if rel in SKIP:
                continue
            old = _committed(rel)
            if old is None:
                errors.append(f"{rel}: not committed")
                continue
            n += 1
            if rel.endswith(".json"):
                errors += _cmp_json(json.loads(p.read_text(encoding="utf-8")), json.loads(old), rel)
            else:
                errors += _cmp_csv(pd.read_csv(p), pd.read_csv(io.StringIO(old)), rel)
    print(f"compared {n} files, {len(errors)} differences")
    for e in errors[:50]:
        print("  DRIFT", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
