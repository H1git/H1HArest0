"""Einfache Flask-Todo-Anwendung mit HTML-Ansicht, JSON-API und Persistenz."""

from itertools import count
import json
import os
from pathlib import Path
from typing import List, TypedDict

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for


class Todo(TypedDict):
    id: int
    title: str
    done: bool
    state: str
    comment: str


app = Flask(__name__)

_id_counter = count(1)
todos: List[Todo] = []
data_file: Path | None = None
ALLOWED_STATES = {"idle", "inwork"}


def _normalize_state(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in ALLOWED_STATES else "idle"


def _normalize_comment(value: str) -> str:
    return value.strip()


def _normalize_todo(raw: dict) -> Todo:
    return Todo(
        id=int(raw.get("id", 0)),
        title=str(raw.get("title", "")).strip(),
        done=bool(raw.get("done", False)),
        state=_normalize_state(str(raw.get("state", "idle"))),
        comment=_normalize_comment(str(raw.get("comment", ""))),
    )


def _load_from_file() -> None:
    """Lädt Todos von der Festplatte und aktualisiert den ID-Zähler."""
    global _id_counter

    if data_file is None:
        return

    todos.clear()
    if data_file.exists():
        try:
            loaded = json.loads(data_file.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                todos.extend(
                    _normalize_todo(todo)
                    for todo in loaded
                    if isinstance(todo, dict)
                )
        except (OSError, json.JSONDecodeError):
            pass

    max_id = max((todo["id"] for todo in todos), default=0)
    _id_counter = count(max_id + 1)


def _save_to_file() -> None:
    if data_file is None:
        return
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(
        json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_data_file(path: Path) -> None:
    """Setzt die Datei für die Persistenz und lädt bestehende Todos."""
    global data_file
    data_file = path
    data_file.parent.mkdir(parents=True, exist_ok=True)
    _load_from_file()


DEFAULT_DATA_FILE = Path(
    os.environ.get("TODO_DATA_FILE", Path(__file__).parent / "data" / "todos.json")
)
set_data_file(DEFAULT_DATA_FILE)


def _get_todo(todo_id: int) -> Todo | None:
    for todo in todos:
        if todo["id"] == todo_id:
            return todo
    return None


def _next_id() -> int:
    return next(_id_counter)


def reset_state() -> None:
    """Setzt Todos und ID-Zähler zurück und leert die Persistenz."""
    global _id_counter
    todos.clear()
    _id_counter = count(1)
    if data_file and data_file.exists():
        try:
            data_file.unlink()
        except OSError:
            pass
    _save_to_file()


@app.get("/")
def index():
    return render_template("todos.html", todos=todos)


@app.post("/add")
def add_todo():
    title = request.form.get("title", "").strip()
    state = _normalize_state(request.form.get("state", "idle"))
    comment = _normalize_comment(request.form.get("comment", ""))
    if title:
        todos.append(
            Todo(id=_next_id(), title=title, done=False, state=state, comment=comment)
        )
        _save_to_file()
    return redirect(url_for("index"))


@app.post("/toggle/<int:todo_id>")
def toggle_todo(todo_id: int):
    todo = _get_todo(todo_id)
    if todo is not None:
        todo["done"] = not todo["done"]
        _save_to_file()
    return redirect(url_for("index"))


@app.post("/delete/<int:todo_id>")
def delete_todo(todo_id: int):
    todo = _get_todo(todo_id)
    if todo is not None:
        todos.remove(todo)
        _save_to_file()
    return redirect(url_for("index"))


@app.get("/api/todos")
def list_todos():
    return jsonify(todos)


@app.post("/api/todos")
def create_todo():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        abort(400, description="title erforderlich")
    state = _normalize_state(str(data.get("state", "idle")))
    comment = _normalize_comment(str(data.get("comment", "")))
    todo = Todo(id=_next_id(), title=title, done=False, state=state, comment=comment)
    todos.append(todo)
    _save_to_file()
    return jsonify(todo), 201


@app.patch("/api/todos/<int:todo_id>")
def update_todo(todo_id: int):
    data = request.get_json(silent=True) or {}
    done = data.get("done")
    state = data.get("state")
    comment = data.get("comment")

    todo = _get_todo(todo_id)
    if todo is None:
        abort(404, description="Todo nicht gefunden")

    if done is not None:
        todo["done"] = bool(done)
    if state is not None:
        todo["state"] = _normalize_state(str(state))
    if comment is not None:
        todo["comment"] = _normalize_comment(str(comment))
    if done is not None or state is not None or comment is not None:
        _save_to_file()
    return jsonify(todo)


@app.delete("/api/todos/<int:todo_id>")
def delete_todo_api(todo_id: int):
    todo = _get_todo(todo_id)
    if todo is None:
        abort(404, description="Todo nicht gefunden")
    todos.remove(todo)
    _save_to_file()
    return ("", 204)


# region Server starten:
if __name__ == "__main__":
    # SSL optional schaltbar: USE_SSL=0 für reines HTTP
    use_ssl = False
    ssl_ctx = ("certs/cert.pem", "certs/key.pem") if use_ssl else None

    try:
        port = 8063
        app.run(host="0.0.0.0", port=port, debug=True, ssl_context=ssl_ctx)
    except:
        port = 8064
        app.run(host="0.0.0.0", port=port, debug=True, ssl_context=ssl_ctx)

# endregion
