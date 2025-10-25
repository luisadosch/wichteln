import importlib
import sys
from datetime import datetime

import pytest


@pytest.fixture
def app_module(monkeypatch, tmp_path):
    db_path = tmp_path / "wichteln_test.db"
    monkeypatch.setenv("WICHTEL_DB_PATH", str(db_path))

    if "wichtel" in sys.modules:
        del sys.modules["wichtel"]

    module = importlib.import_module("wichtel")
    return module


def test_save_and_load_round_trip(app_module):
    assignments = [
        {"name": "Anna", "code": "ABC123", "receiver": "Ben"},
        {"name": "Ben", "code": "XYZ789", "receiver": "Anna"},
    ]
    pairs = [["Anna", "Ben"]]

    app_module.save_session_to_db("Stern123", assignments, pairs)

    loaded = app_module.load_session_from_db("Stern123")
    assert loaded is not None
    assert loaded["assignments"] == assignments
    assert loaded["pairs"] == pairs
    assert loaded["user_password"] == "Stern123"


def test_list_sessions_for_admin(app_module):
    assignments = [{"name": "Carla", "code": "QWE456", "receiver": "Daniel"}]
    pairs = []

    app_module.save_session_to_db("Mond987", assignments, pairs)

    sessions = app_module.list_sessions_for_admin()
    assert len(sessions) == 1

    session = sessions[0]
    assert session["user_password"] == "Mond987"
    assert session["participant_count"] == len(assignments)
    assert session["pairs"] == pairs
    assert session["assignments"] == assignments
    # ISO-8601 Datum prüfen
    datetime.fromisoformat(session["created_at"])
