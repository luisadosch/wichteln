import importlib
import itertools
import sys
from datetime import datetime
from pathlib import Path

import pytest
import requests


@pytest.fixture
def app_module(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    store: dict[str, dict[str, str]] = {}
    id_counter = itertools.count(1)

    class FakeResponse:
        def __init__(self, status_code=200, data=None, headers=None, text=""):
            self.status_code = status_code
            self._data = data or []
            self.headers = headers or {}
            self.text = text

        def json(self):
            return self._data

    def fake_post(url, *, headers=None, json=None, params=None, timeout=None):  # type: ignore[override]
        if url.endswith("/rest/v1/rpc/sql"):
            return FakeResponse()
        if url.endswith("/rest/v1/sessions"):
            if not json:
                raise AssertionError("Expected payload for upsert")
            record = json[0].copy()
            key = record["user_password_hash"]
            existing = store.get(key)
            if existing:
                record["id"] = existing["id"]
            else:
                record["id"] = next(id_counter)
            store[key] = record
            return FakeResponse(status_code=201)
        raise AssertionError(f"Unexpected POST URL {url}")

    def fake_get(url, *, headers=None, params=None, timeout=None):  # type: ignore[override]
        if url.endswith("/rest/v1/sessions"):
            data = []
            if params:
                filter_fields = [k for k in params.keys() if k not in {"select", "limit"}]
                if filter_fields:
                    field = filter_fields[0]
                    filter_value = params[field]
                    if isinstance(filter_value, str) and filter_value.startswith("eq."):
                        target = filter_value[3:]
                        for record in store.values():
                            if record.get(field) == target:
                                data = [record]
                                break
            return FakeResponse(data=data)
        raise AssertionError(f"Unexpected GET URL {url}")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

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
