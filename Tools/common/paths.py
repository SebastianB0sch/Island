"""Repository paths, resolved from this file so every script works from any CWD."""

from __future__ import annotations

from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
PROJECT_DIR = REPO_ROOT / "DuelAcademyIsland"
DATA_DIR = PROJECT_DIR / "Content" / "Data"
DOCS_DIR = REPO_ROOT / "Docs"
UPROJECT = PROJECT_DIR / "DuelAcademyIsland.uproject"
