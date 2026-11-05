"""Shared stdlib-only helpers for the Python data tools.

Script folders (canon, effects, economy, validate, ...) put the ``Tools``
directory on ``sys.path`` exactly like they put their own folder on it, then
import from here:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tooling import atomic
"""
