"""Load an experiment package from disk and hash everything on the way in.

Reading is a verification step: a file that will not parse against the schema
is a finding, not an exception to swallow.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from agent.schemas import (
    ClaimedAnalysis,
    Convention,
    CountRow,
    ExperimentPackage,
    Manifest,
)

RAW_COUNTS = "raw_counts.csv"
CONVENTION = "convention.json"
CLAIM = "claimed_analysis.json"
MANIFEST = "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"required artifact missing: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_counts(path: Path) -> list[CountRow]:
    if not path.exists():
        raise FileNotFoundError(f"required artifact missing: {path.name}")
    rows: list[CountRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            raw_flags = (record.get("flags") or "").strip()
            rows.append(
                CountRow(
                    block_id=record["block_id"].strip(),
                    subrun_id=record["subrun_id"].strip(),
                    setting_a=record["setting_a"].strip(),
                    setting_b=record["setting_b"].strip(),
                    n_pp=int(record["n_pp"]),
                    n_pm=int(record["n_pm"]),
                    n_mp=int(record["n_mp"]),
                    n_mm=int(record["n_mm"]),
                    window_ns=float(record["window_ns"]),
                    flags=tuple(f for f in raw_flags.split("|") if f),
                )
            )
    if not rows:
        raise ValueError(f"{path.name} contains no acquisition rows")
    return rows


def read_package(root: str | Path) -> ExperimentPackage:
    """Parse and validate every artifact in a submitted package."""
    base = Path(root)
    if not base.is_dir():
        raise NotADirectoryError(f"package root is not a directory: {base}")
    return ExperimentPackage(
        root=str(base),
        manifest=Manifest.model_validate(_load_json(base / MANIFEST)),
        counts=read_counts(base / RAW_COUNTS),
        convention=Convention.model_validate(_load_json(base / CONVENTION)),
        claim=ClaimedAnalysis.model_validate(_load_json(base / CLAIM)),
    )


def hash_package(root: str | Path) -> dict[str, str]:
    """sha256 of every file actually present in the package directory."""
    base = Path(root)
    return {
        path.relative_to(base).as_posix(): sha256_file(path)
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }
