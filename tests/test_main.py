import json
import tempfile
from pathlib import Path

import main

_tmpdir = None


def setup_function(_):
    global _tmpdir
    if _tmpdir:
        _tmpdir.cleanup()
    _tmpdir = tempfile.TemporaryDirectory()
    data_file = Path(_tmpdir.name) / "todos.json"
    main.set_data_file(data_file)
    main.reset_state()
    main.app.testing = True


def teardown_function(_):
    global _tmpdir
    if _tmpdir:
        _tmpdir.cleanup()
        _tmpdir = None


def test_html_add_toggle_delete():
    client = main.app.test_client()

    # neue Aufgabe hinzufügen
    client.post("/add", data={"title": "Erste Aufgabe"})
    response = client.get("/")
    assert b"Erste Aufgabe" in response.data

    # Aufgabe als erledigt markieren
    first_id = main.todos[0]["id"]
    client.post(f"/toggle/{first_id}")
    assert main.todos[0]["done"] is True

    # Aufgabe löschen
    client.post(f"/delete/{first_id}")
    assert main.todos == []


def test_api_crud_flow():
    client = main.app.test_client()

    # erstellen
    create_resp = client.post(
        "/api/todos",
        data=json.dumps({"title": "API Aufgabe"}),
        content_type="application/json",
    )
    assert create_resp.status_code == 201
    created = create_resp.get_json()
    todo_id = created["id"]

    # auflisten
    list_resp = client.get("/api/todos")
    assert list_resp.status_code == 200
    assert len(list_resp.get_json()) == 1

    # aktualisieren
    patch_resp = client.patch(
        f"/api/todos/{todo_id}",
        data=json.dumps({"done": True}),
        content_type="application/json",
    )
    assert patch_resp.status_code == 200
    assert patch_resp.get_json()["done"] is True

    # löschen
    delete_resp = client.delete(f"/api/todos/{todo_id}")
    assert delete_resp.status_code == 204
    assert main.todos == []
