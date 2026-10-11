import json
import mimetypes
import os
import sqlite3
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


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


class TodoRequestHandler(BaseHTTPRequestHandler):
    server_version = "TodoApp/1.0"

    @property
    def store(self):
        return self.server.store

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/api/todos":
            self._send_json(HTTPStatus.OK, self.store.list_todos())
            return

        static_file = STATIC_FILES.get(path)
        if static_file is None or not static_file.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(static_file.name)[0] or "application/octet-stream"
        content = static_file.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/todos":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        body = self._read_json()
        if body is None:
            return
        title = body.get("title") if isinstance(body, dict) else None
        if not isinstance(title, str) or not title.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "A todo title is required."})
            return
        title = title.strip()
        if len(title) > MAX_TITLE_LENGTH:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": f"Todo titles must be {MAX_TITLE_LENGTH} characters or fewer."},
            )
            return

        self._send_json(HTTPStatus.CREATED, self.store.add_todo(title))

    def do_PATCH(self):
        todo_id = self._todo_id_from_path()
        if todo_id is None:
            return

        body = self._read_json()
        if body is None:
            return
        completed = body.get("completed") if isinstance(body, dict) else None
        if not isinstance(completed, bool):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "The completed field must be true or false."},
            )
            return

        todo = self.store.set_completed(todo_id, completed)
        if todo is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Todo not found."})
            return
        self._send_json(HTTPStatus.OK, todo)

    def do_DELETE(self):
        todo_id = self._todo_id_from_path()
        if todo_id is None:
            return
        if not self.store.delete_todo(todo_id):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Todo not found."})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def _todo_id_from_path(self):
        path = urlsplit(self.path).path
        prefix = "/api/todos/"
        if not path.startswith(prefix):
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        try:
            todo_id = int(path[len(prefix):])
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        if todo_id < 1:
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        return todo_id

    def _read_json(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length."})
            return None
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Request is too large."})
            return None
        try:
            body = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."})
            return None
        return body

    def _send_json(self, status, payload):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


def main():
    database_path = os.environ.get("TODO_DB_PATH", APP_DIR / "todos.sqlite3")
    store = TodoStore(database_path)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), TodoRequestHandler)
    server.store = store
    print(f"Todo app running on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down todo app.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
