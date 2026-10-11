import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import TodoRequestHandler, TodoStore


class TodoAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.store = TodoStore(self.database_path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), TodoRequestHandler)
        self.server.store = self.store
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connection = HTTPConnection("127.0.0.1", self.server.server_port)

    def tearDown(self):
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp_dir.cleanup()

    def request_json(self, method, path, payload=None):
        body = json.dumps(payload) if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        self.connection.request(method, path, body=body, headers=headers)
        response = self.connection.getresponse()
        content = response.read()
        return response.status, json.loads(content) if content else None

    def test_add_complete_and_delete_todo(self):
        status, todo = self.request_json("POST", "/api/todos", {"title": "  Write tests  "})
        self.assertEqual(status, 201)
        self.assertEqual(todo["title"], "Write tests")
        self.assertFalse(todo["completed"])

        status, completed = self.request_json(
            "PATCH", f"/api/todos/{todo['id']}", {"completed": True}
        )
        self.assertEqual(status, 200)
        self.assertTrue(completed["completed"])

        status, todos = self.request_json("GET", "/api/todos")
        self.assertEqual(status, 200)
        self.assertEqual(todos, [completed])

        status, body = self.request_json("DELETE", f"/api/todos/{todo['id']}")
        self.assertEqual(status, 204)
        self.assertIsNone(body)
        self.assertEqual(self.request_json("GET", "/api/todos")[1], [])

    def test_todos_persist_after_store_is_reopened(self):
        status, todo = self.request_json("POST", "/api/todos", {"title": "Persist me"})
        self.assertEqual(status, 201)

        reopened_store = TodoStore(self.database_path)
        self.assertEqual(reopened_store.list_todos()[0]["id"], todo["id"])
        self.assertEqual(reopened_store.list_todos()[0]["title"], "Persist me")

    def test_invalid_todo_title_is_rejected(self):
        status, body = self.request_json("POST", "/api/todos", {"title": "   "})
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertEqual(self.store.list_todos(), [])

    def test_missing_todo_returns_not_found(self):
        status, body = self.request_json("PATCH", "/api/todos/999", {"completed": True})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "Todo not found.")

    def test_serves_app_assets(self):
        for path, expected_content_type in (
            ("/", "text/html"),
            ("/app.js", "text/javascript"),
            ("/styles.css", "text/css"),
        ):
            with self.subTest(path=path):
                self.connection.request("GET", path)
                response = self.connection.getresponse()
                content = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(expected_content_type, response.getheader("Content-Type"))
                self.assertTrue(content)


if __name__ == "__main__":
    unittest.main()
