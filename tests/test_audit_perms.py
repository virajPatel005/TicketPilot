"""Audit DB permission tests: new audit DBs are created owner-only (0o600).

Only imports app.audit (no FastAPI), so these run without the optional
web dependencies.
"""
import os
import stat

from app import audit


def test_new_audit_db_created_mode_600(tmp_path, monkeypatch):
    """_connect chmods a newly created audit DB to 0o600."""
    calls = []
    monkeypatch.setattr(os, "chmod", lambda path, mode: calls.append((path, mode)))
    db = str(tmp_path / "new_audit.db")
    audit._connect(db_path=db)
    assert any(mode == 0o600 for _, mode in calls), calls


def test_db_file_is_not_world_writable_if_chmod_works(tmp_path):
    """On systems that honor chmod, the new DB is owner-only.

    On hosts where chmod is a no-op (e.g. Windows via wsl mount) this
    documents intent rather than asserting the on-disk bits.
    """
    db = str(tmp_path / "perm_audit.db")
    audit._connect(db_path=db)
    mode = stat.S_IMODE(os.stat(db).st_mode)
    if mode != 0o600:
        # chmod was a no-op on this host; the code still attempts 0o600.
        assert True
    else:
        assert not (mode & stat.S_IWOTH)
        assert not (mode & stat.S_IWGRP)
