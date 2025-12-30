"""Einfache Flask-Todo-Anwendung mit HTML-Ansicht und JSON-API.

Starten mit:
    flask --app main run --debug
"""

from itertools import count
from typing import List, TypedDict

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for


class Todo(TypedDict):
    id: int
    title: str
    done: bool


app = Flask(__name__)

_id_counter = count(1)
todos: List[Todo] = []


def _get_todo(todo_id: int) -> Todo | None:
    for todo in todos:
        if todo["id"] == todo_id:
            return todo
    return None


def _next_id() -> int:
    return next(_id_counter)


def reset_state() -> None:
    """Nur für Tests: setzt Todos und ID-Zähler zurück."""
    global _id_counter
    todos.clear()
    _id_counter = count(1)


@app.get("/")
def index():
    return render_template("todos.html", todos=todos)


@app.post("/add")
def add_todo():
    title = request.form.get("title", "").strip()
    if title:
        todos.append(Todo(id=_next_id(), title=title, done=False))
    return redirect(url_for("index"))


@app.post("/toggle/<int:todo_id>")
def toggle_todo(todo_id: int):
    todo = _get_todo(todo_id)
    if todo is not None:
        todo["done"] = not todo["done"]
    return redirect(url_for("index"))


@app.post("/delete/<int:todo_id>")
def delete_todo(todo_id: int):
    todo = _get_todo(todo_id)
    if todo is not None:
        todos.remove(todo)
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
    todo = Todo(id=_next_id(), title=title, done=False)
    todos.append(todo)
    return jsonify(todo), 201


@app.patch("/api/todos/<int:todo_id>")
def update_todo(todo_id: int):
    data = request.get_json(silent=True) or {}
    done = data.get("done")

    todo = _get_todo(todo_id)
    if todo is None:
        abort(404, description="Todo nicht gefunden")

    if done is not None:
        todo["done"] = bool(done)
    return jsonify(todo)


@app.delete("/api/todos/<int:todo_id>")
def delete_todo_api(todo_id: int):
    todo = _get_todo(todo_id)
    if todo is None:
        abort(404, description="Todo nicht gefunden")
    todos.remove(todo)
    return ("", 204)


if __name__ == "__main__":
    app.run(debug=True)
