"""Einfache Flask-Todo-Anwendung mit HTML-Ansicht, JSON-API und Persistenz."""

from itertools import count
import json
import os
from pathlib import Path
from typing import Dict, List, TypedDict

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for


class Todo(TypedDict):
    id: int
    title: str
    done: bool
    state: str
    comment: str


app = Flask(__name__)

_list_states: Dict[str, Dict[str, object]] = {}
data_dir: Path = Path(__file__).parent / "data"
legacy_data_file: Path | None = None
CONFIG_FILE = Path(__file__).parent / "config.yaml"
ALLOWED_STATES = {"leerlauf", "in arbeit", "geplant"}


def _parse_simple_config(path: Path) -> Dict[str, Dict[str, str]]:
    data: Dict[str, Dict[str, str]] = {"lists": {}}
    current_section = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and ":" not in line[:-1]:
            current_section = line[:-1].strip()
            data.setdefault(current_section, {})
            continue
        if current_section == "lists" and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith(("'", '"')) and value.endswith(("'", '"')):
                value = value[1:-1]
            if key:
                data["lists"][key] = value
    return data


def _load_config() -> Dict[str, Dict[str, str]]:
    if CONFIG_FILE.exists():
        try:
            return _parse_simple_config(CONFIG_FILE)
        except OSError:
            pass
    return {"lists": {"default": "Todos"}}


CONFIG = _load_config()
LISTS: Dict[str, str] = CONFIG.get("lists", {}) or {"default": "Todos"}


def _normalize_state(value: str) -> str:
    normalized = value.strip().lower()

    if normalized in ALLOWED_STATES:
        ret = value
    else:
        ret = "Leerlauf"
    # ret = normalized if normalized in ALLOWED_STATES else "Leerlauf"
    return ret


def _normalize_comment(value: str) -> str:
    return value.strip()


def _normalize_todo(raw: dict) -> Todo:
    return Todo(
        id=int(raw.get("id", 0)),
        title=str(raw.get("title", "")).strip(),
        done=bool(raw.get("done", False)),
        state=_normalize_state(str(raw.get("state", "Leerlauf"))),
        comment=_normalize_comment(str(raw.get("comment", ""))),
    )


def _default_list_id() -> str:
    return next(iter(LISTS.keys()))


def _list_data_file(list_id: str) -> Path:
    if legacy_data_file and list_id == _default_list_id():
        return legacy_data_file
    return data_dir / f"{list_id}.json"


def _ensure_list_loaded(list_id: str) -> None:
    if list_id in _list_states:
        return
    _load_from_file(list_id)


def _get_list(list_id: str) -> List[Todo]:
    _ensure_list_loaded(list_id)
    return _list_states[list_id]["todos"]  # type: ignore[return-value]


def get_list(list_id: str) -> List[Todo]:
    return _get_list(list_id)


def _load_from_file(list_id: str) -> None:
    """Lädt Todos von der Festplatte und aktualisiert den ID-Zähler."""
    data_file = _list_data_file(list_id)
    todos: List[Todo] = []

    if data_file.exists():
        try:
            loaded = json.loads(data_file.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                todos.extend(
                    _normalize_todo(todo) for todo in loaded if isinstance(todo, dict)
                )
        except (OSError, json.JSONDecodeError):
            pass

    max_id = max((todo["id"] for todo in todos), default=0)
    _list_states[list_id] = {
        "todos": todos,
        "id_counter": count(max_id + 1),
        "data_file": data_file,
    }


def _save_to_file(list_id: str) -> None:
    state = _list_states.get(list_id)
    if not state:
        return
    data_file = state["data_file"]
    todos = state["todos"]
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(
        json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_data_file(path: Path) -> None:
    """Setzt die Datei für die Persistenz und lädt bestehende Todos."""
    global data_dir, legacy_data_file
    legacy_data_file = path
    data_dir = path.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    _list_states.clear()
    _ensure_list_loaded(_default_list_id())


DEFAULT_DATA_FILE = os.environ.get("TODO_DATA_FILE")
if DEFAULT_DATA_FILE:
    set_data_file(Path(DEFAULT_DATA_FILE))
else:
    data_dir.mkdir(parents=True, exist_ok=True)
    _ensure_list_loaded(_default_list_id())


def _get_todo(list_id: str, todo_id: int) -> Todo | None:
    for todo in _get_list(list_id):
        if todo["id"] == todo_id:
            return todo
    return None


def _next_id(list_id: str) -> int:
    _ensure_list_loaded(list_id)
    return next(_list_states[list_id]["id_counter"])  # type: ignore[return-value]


def reset_state() -> None:
    """Setzt Todos und ID-Zähler zurück und leert die Persistenz."""
    for list_id in LISTS.keys():
        data_file = _list_data_file(list_id)
        if data_file.exists():
            try:
                data_file.unlink()
            except OSError:
                pass
    _list_states.clear()
    _ensure_list_loaded(_default_list_id())


def _resolve_list_id() -> str:
    list_id = request.args.get("list") or request.form.get("list")
    if not list_id or list_id not in LISTS:
        list_id = _default_list_id()
    _ensure_list_loaded(list_id)
    return list_id


@app.get("/")
def index():
    list_id = _resolve_list_id()
    return render_template(
        "todos.html",
        todos=_get_list(list_id),
        list_id=list_id,
        list_title=LISTS.get(list_id, list_id),
        lists=LISTS,
    )


@app.post("/add")
def add_todo():
    list_id = _resolve_list_id()
    title = request.form.get("title", "").strip()
    state = _normalize_state(request.form.get("state", "Leerlauf"))
    comment = _normalize_comment(request.form.get("comment", ""))
    if title:
        _get_list(list_id).append(
            Todo(
                id=_next_id(list_id),
                title=title,
                done=False,
                state=state,
                comment=comment,
            )
        )
        _save_to_file(list_id)
    return redirect(url_for("index", list=list_id))


@app.post("/toggle/<int:todo_id>")
def toggle_todo(todo_id: int):
    list_id = _resolve_list_id()
    todo = _get_todo(list_id, todo_id)
    if todo is not None:
        todo["done"] = not todo["done"]
        _save_to_file(list_id)
    return redirect(url_for("index", list=list_id))


@app.post("/update/<int:todo_id>")
def update_todo_html(todo_id: int):
    list_id = _resolve_list_id()
    todo = _get_todo(list_id, todo_id)
    if todo is not None:
        title = request.form.get("title", "").strip()
        if title:
            todo["title"] = title
        todo["state"] = _normalize_state(request.form.get("state", "Leerlauf"))
        todo["comment"] = _normalize_comment(request.form.get("comment", ""))
        _save_to_file(list_id)
    return redirect(url_for("index", list=list_id))


@app.post("/delete/<int:todo_id>")
def delete_todo(todo_id: int):
    list_id = _resolve_list_id()
    todo = _get_todo(list_id, todo_id)
    if todo is not None:
        _get_list(list_id).remove(todo)
        _save_to_file(list_id)
    return redirect(url_for("index", list=list_id))


@app.get("/api/todos")
def list_todos():
    list_id = _resolve_list_id()
    return jsonify(_get_list(list_id))


@app.post("/api/todos")
def create_todo():
    list_id = _resolve_list_id()
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        abort(400, description="title erforderlich")
    state = _normalize_state(str(data.get("state", "Leerlauf")))
    comment = _normalize_comment(str(data.get("comment", "")))
    todo = Todo(
        id=_next_id(list_id),
        title=title,
        done=False,
        state=state,
        comment=comment,
    )
    _get_list(list_id).append(todo)
    _save_to_file(list_id)
    return jsonify(todo), 201


@app.patch("/api/todos/<int:todo_id>")
def update_todo(todo_id: int):
    list_id = _resolve_list_id()
    data = request.get_json(silent=True) or {}
    done = data.get("done")
    title = data.get("title")
    state = data.get("state")
    comment = data.get("comment")

    todo = _get_todo(list_id, todo_id)
    if todo is None:
        abort(404, description="Todo nicht gefunden")

    if title is not None:
        normalized_title = str(title).strip()
        if normalized_title:
            todo["title"] = normalized_title
    if done is not None:
        todo["done"] = bool(done)
    if state is not None:
        todo["state"] = _normalize_state(str(state))
    if comment is not None:
        todo["comment"] = _normalize_comment(str(comment))
    if (
        title is not None
        or done is not None
        or state is not None
        or comment is not None
    ):
        _save_to_file(list_id)
    return jsonify(todo)


@app.delete("/api/todos/<int:todo_id>")
def delete_todo_api(todo_id: int):
    list_id = _resolve_list_id()
    todo = _get_todo(list_id, todo_id)
    if todo is None:
        abort(404, description="Todo nicht gefunden")
    _get_list(list_id).remove(todo)
    _save_to_file(list_id)
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
