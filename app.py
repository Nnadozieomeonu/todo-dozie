import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge


APP_DIR = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": APP_DIR / "index.html",
    "/app.js": APP_DIR / "app.js",
    "/styles.css": APP_DIR / "styles.css",
}
MAX_REQUEST_BYTES = 1024 * 1024
MAX_TITLE_LENGTH = 200


class TodoStore:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0
                        CHECK (completed IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _as_todo(row):
        return {
            "id": row["id"],
            "title": row["title"],
            "completed": bool(row["completed"]),
            "created_at": row["created_at"],
        }

    def list_todos(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, title, completed, created_at FROM todos ORDER BY id DESC"
            ).fetchall()
        return [self._as_todo(row) for row in rows]

    def add_todo(self, title):
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO todos (title) VALUES (?)", (title,)
            )
            row = connection.execute(
                "SELECT id, title, completed, created_at FROM todos WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._as_todo(row)

    def set_completed(self, todo_id, completed):
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE todos SET completed = ? WHERE id = ?",
                (int(completed), todo_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT id, title, completed, created_at FROM todos WHERE id = ?",
                (todo_id,),
            ).fetchone()
        return self._as_todo(row)

    def delete_todo(self, todo_id):
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        return cursor.rowcount > 0


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
app.config["TODO_STORE"] = TodoStore(
    os.environ.get("TODO_DB_PATH", APP_DIR / "todos.sqlite3")
)


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify(error="Request is too large."), 413


@app.get("/")
def index():
    return send_file(STATIC_FILES["/"])


@app.get("/app.js")
def javascript():
    return send_file(STATIC_FILES["/app.js"])


@app.get("/styles.css")
def stylesheet():
    return send_file(STATIC_FILES["/styles.css"])


@app.get("/api/todos")
def list_todos():
    return jsonify(app.config["TODO_STORE"].list_todos())


def read_json_body():
    try:
        return request.get_json(force=True), None
    except BadRequest:
        return None, (jsonify(error="Request body must be valid JSON."), 400)


@app.post("/api/todos")
def add_todo():
    body, error_response = read_json_body()
    if error_response:
        return error_response
    title = body.get("title") if isinstance(body, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="A todo title is required."), 400
    title = title.strip()
    if len(title) > MAX_TITLE_LENGTH:
        return jsonify(
            error=f"Todo titles must be {MAX_TITLE_LENGTH} characters or fewer."
        ), 400
    todo = app.config["TODO_STORE"].add_todo(title)
    return jsonify(todo), 201


@app.patch("/api/todos/<int:todo_id>")
def update_todo(todo_id):
    body, error_response = read_json_body()
    if error_response:
        return error_response
    completed = body.get("completed") if isinstance(body, dict) else None
    if not isinstance(completed, bool):
        return jsonify(error="The completed field must be true or false."), 400
    todo = app.config["TODO_STORE"].set_completed(todo_id, completed)
    if todo is None:
        return jsonify(error="Todo not found."), 404
    return jsonify(todo)


@app.delete("/api/todos/<int:todo_id>")
def delete_todo(todo_id):
    if not app.config["TODO_STORE"].delete_todo(todo_id):
        return jsonify(error="Todo not found."), 404
    return "", 204


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Todo app running on {host}:{port}")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
