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
    admin_code = "SESSIONCODE1"

    app_module.save_session_to_db("Stern123", admin_code, assignments, pairs)

    loaded = app_module.load_session_from_db("Stern123")
    assert loaded is not None
    assert loaded["assignments"] == assignments
    assert loaded["pairs"] == pairs
    assert loaded["user_password"] == "Stern123"

    admin_view = app_module.load_session_from_admin_code(admin_code)
    assert admin_view is not None
    assert admin_view["assignments"] == assignments
    assert admin_view["pairs"] == pairs
    assert admin_view["user_password"] == "Stern123"
    datetime.fromisoformat(admin_view["created_at"])


def test_invalid_admin_code(app_module):
    assignments = [{"name": "Carla", "code": "QWE456", "receiver": "Daniel"}]
    pairs = []

    app_module.save_session_to_db("Mond987", "SESSIONCODE2", assignments, pairs)

    assert app_module.load_session_from_admin_code("WRONGCODE") is None
