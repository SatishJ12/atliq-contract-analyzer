"""Loads the AtliQ synthetic dataset and turns contracts into citable clauses.

Everything the analyzer says must point back to a file in this dataset, so this
module keeps file names and clause numbers attached to every piece of text.
"""
from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent

# "Today" in the synthetic dataset. Used for expiry / restricted-period maths.
DATASET_TODAY = date(2026, 9, 28)


def _resolve_data_dir() -> Path:
    candidates = [
        os.environ.get("ATLIQ_DATA_DIR"),
        APP_DIR / "data",
        Path("/mnt/project-files/deliverables/contract-analyzer/data"),
        Path("/mnt/project-files/converted"),
    ]
    for c in candidates:
        if c and Path(c).exists() and (Path(c) / "contract_tracker.csv").exists():
            return Path(c)
    return APP_DIR / "data"


DATA_DIR = _resolve_data_dir()
SIGNED_DIR = DATA_DIR / "signed_contracts"
INCOMING_DIR = DATA_DIR / "incoming"
DEMO_UPLOADS_DIR = DATA_DIR / "demo_uploads"  # held back for live upload demos; never scanned
NOTES_DIR = DATA_DIR / "meeting_notes"


# --------------------------------------------------------------------------- #
# Clause model
# --------------------------------------------------------------------------- #
@dataclass
class Clause:
    ref: str            # e.g. "12.1" or "§ 6.3" or "Annexure B"
    heading: str        # enclosing section heading, e.g. "12. RESTRICTIVE COVENANTS"
    text: str
    source: str = ""    # file name the clause came from

    def cite(self) -> str:
        loc = f"cl. {self.ref}" if self.ref else self.heading
        return f"{self.source} — {loc}" if self.source else loc


_CLAUSE_START = re.compile(
    r"^\s*(?:\*\*)?(?:§\s*)?(\d{1,2}(?:\.\d{1,2}){1,3})\.?(?:\*\*)?\s+"
)
_HEADING = re.compile(r"^\s*#{1,4}\s+(.*)$")
_PLAIN_HEADING = re.compile(r"^\s*(\d{1,2})\.\s+([A-Z][A-Z0-9 ,&'/()\-]{3,})\s*$")


def split_clauses(text: str, source: str = "") -> list[Clause]:
    """Split a markdown/plain contract into numbered clauses.

    Lines that start with a clause number (1.2, 12.4, § 6.3) open a new clause;
    following lines are appended until the next clause or heading. Tables and
    unnumbered paragraphs under a heading become a clause whose ref is the heading.
    """
    clauses: list[Clause] = []
    heading = ""
    cur: Clause | None = None

    def flush():
        nonlocal cur
        if cur and cur.text.strip():
            cur.text = re.sub(r"[ \t]+", " ", cur.text.strip())
            clauses.append(cur)
        cur = None

    for raw in text.splitlines():
        line = raw.rstrip()
        h = _HEADING.match(line) or _PLAIN_HEADING.match(line)
        if h:
            flush()
            heading = (h.group(1) if h.re is _HEADING else f"{h.group(1)}. {h.group(2)}").strip().strip("*")
            continue
        m = _CLAUSE_START.match(line)
        if m:
            flush()
            cur = Clause(ref=m.group(1), heading=heading, text=line.strip(), source=source)
            continue
        if not line.strip():
            if cur and not cur.ref:
                flush()
            continue
        if cur is None:
            cur = Clause(ref="", heading=heading, text=line.strip(), source=source)
        else:
            cur.text += "\n" + line.strip()
    flush()
    return clauses


# --------------------------------------------------------------------------- #
# Dataset access
# --------------------------------------------------------------------------- #
def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


@lru_cache(maxsize=1)
def load_tracker() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "contract_tracker.csv", dtype=str).fillna("")
    return df


def list_incoming() -> list[Path]:
    return sorted(INCOMING_DIR.glob("*.md")) if INCOMING_DIR.exists() else []


def list_signed() -> list[Path]:
    return sorted(SIGNED_DIR.glob("*.md")) if SIGNED_DIR.exists() else []


@lru_cache(maxsize=1)
def signed_clauses() -> list[Clause]:
    out: list[Clause] = []
    for p in list_signed():
        out.extend(split_clauses(read_text(p), source=p.name))
    return out


@lru_cache(maxsize=1)
def load_register() -> list[dict]:
    path = APP_DIR / "commitment_register.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_playbook_docs() -> dict[str, str]:
    """Context documents that describe how AtliQ reviews and has negotiated."""
    docs = {}
    for name in ["karandeep_contract_checklist.md", "atliq_entities.md", "negotiation_notes.md"]:
        p = DATA_DIR / name
        if p.exists():
            docs[name] = read_text(p)
    return docs


@lru_cache(maxsize=1)
def load_meeting_notes() -> dict[str, str]:
    if not NOTES_DIR.exists():
        return {}
    return {p.name: read_text(p) for p in sorted(NOTES_DIR.glob("*.md"))}


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def extract_text_from_upload(name: str, data: bytes) -> str:
    """PDF (pdfplumber), DOCX (python-docx), or plain text / markdown."""
    lower = name.lower()
    if lower.endswith(".pdf"):
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    if lower.endswith(".docx"):
        import docx

        d = docx.Document(io.BytesIO(data))
        lines = []
        for para in d.paragraphs:
            style = (para.style.name or "").lower() if para.style is not None else ""
            txt = para.text.strip()
            if not txt:
                lines.append("")
            elif style.startswith("heading"):
                lines.append(f"## {txt}")
            else:
                lines.append(txt)
        for table in d.tables:
            for row in table.rows:
                lines.append("| " + " | ".join(c.text.strip() for c in row.cells) + " |")
        return "\n".join(lines)
    return data.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Tracker matching
# --------------------------------------------------------------------------- #
_STOP = {"inc", "ltd", "pvt", "llc", "gmbh", "co", "group", "the", "and", "&", "systems",
         "technologies", "hotels", "resorts", "health", "capital", "analytics", "data", "labs"}


def _name_tokens(name: str) -> list[str]:
    toks = re.findall(r"[a-z]+", name.lower())
    return [t for t in toks if t not in _STOP and len(t) > 2]


def match_tracker_rows(text: str, filename: str = "") -> pd.DataFrame:
    """Find tracker rows for the counterparty of this document.

    Matches on the distinctive word of the counterparty name appearing in the
    file name or the first part of the contract (the parties block).
    """
    df = load_tracker()
    head = (filename + " " + text[:3000]).lower()
    scores = {}
    for cp in df["counterparty"].unique():
        if "atliq" in cp.lower():
            continue
        toks = _name_tokens(cp)
        if toks and all(t in head for t in toks[:1]):
            scores[cp] = sum(t in head for t in toks)
    if not scores:
        return df.iloc[0:0]
    best = max(scores.values())
    names = [k for k, v in scores.items() if v == best]
    return df[df["counterparty"].isin(names)]


def related_notes(counterparty: str) -> list[tuple[str, str]]:
    """Lines from meeting notes and negotiation notes that mention the counterparty."""
    toks = _name_tokens(counterparty)
    if not toks:
        return []
    key = toks[0]
    hits = []
    sources = dict(load_meeting_notes())
    neg = load_playbook_docs().get("negotiation_notes.md")
    if neg:
        sources["negotiation_notes.md"] = neg
    for name, body in sources.items():
        if key not in body.lower():
            continue
        if name == "negotiation_notes.md":
            # whole block for that counterparty
            for block in body.split("\n**"):
                if key in block.lower().split("\n")[0]:
                    hits.append((name, "**" + block.strip()))
        else:
            hits.append((name, body.strip()))
    return hits
