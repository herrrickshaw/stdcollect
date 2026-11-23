import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


import os
import shutil

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def analysis(tmp_path, monkeypatch):
    """Run an analysis/*.py script as a program, inside a scratch copy of the repo layout.

    Each script does `os.chdir(<script dir>/..)` and reads/writes relative paths, so it would
    otherwise operate on the committed catalog/ and analysis/ CSVs. We chdir into tmp_path
    first and turn os.chdir into a no-op; the real source is compiled under its real filename
    so coverage is attributed to the repo file.
    """
    (tmp_path / "catalog").mkdir()
    (tmp_path / "analysis").mkdir()
    shutil.copy(REPO / "analysis" / "link_standards.py", tmp_path / "analysis" / "link_standards.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "chdir", lambda p: None)

    def run(name):
        real = REPO / "analysis" / name
        ns = {"__name__": f"analysis_{real.stem}", "__file__": str(real)}
        exec(compile(real.read_text(encoding="utf-8"), str(real), "exec"), ns)
        return ns

    run.root = tmp_path
    return run
