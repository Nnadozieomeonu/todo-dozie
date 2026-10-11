# Today, sorted

A lightweight todo app with a Python standard-library web server and a SQLite database stored in a single file.

## Run the app

Requires Python 3.10 or newer. From this folder, run:

```powershell
python app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Todo items are stored in `todos.sqlite3` beside `app.py` and remain available after restarting the app.

To store the database elsewhere, set `TODO_DB_PATH` before starting the server:

```powershell
$env:TODO_DB_PATH = "C:\path\to\todos.sqlite3"
python app.py
```

## Run tests

```powershell
python -m unittest
```
