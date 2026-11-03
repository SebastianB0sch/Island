"""Shared helpers for the Tools/ data scripts (stdlib only).

Scripts run as ``python Tools/<area>/<script>.py`` put only their own folder on
sys.path. Make this package importable with:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Tools/
    from common.paths import REPO_ROOT, DATA_DIR
    from common.jsonio import read_json, write_json
"""
