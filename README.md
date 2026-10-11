# Todo List

A lightweight todo app built with Flask and SQLite, served by Gunicorn in production.

## Run the app

Requires Python 3.10 or newer. Install the dependencies and run locally:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Todo items are stored in `todos.sqlite3` beside `app.py` and remain available after restarting the app.

To store the database elsewhere, set `TODO_DB_PATH` before starting the server:

```powershell
$env:TODO_DB_PATH = "C:\path\to\todos.sqlite3"
python app.py
```

## Deploy to Heroku

You need a [Heroku account](https://signup.heroku.com/) and the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed. From the project folder:

1. Sign in and create a Heroku app:

   ```powershell
   heroku login
   heroku create your-unique-app-name
   ```

2. Set the Python buildpack and a writable location for the SQLite file:

   ```powershell
   heroku buildpacks:set heroku/python -a your-unique-app-name
   heroku config:set TODO_DB_PATH=/tmp/todos.sqlite3 -a your-unique-app-name
   ```

3. Ensure `Procfile` contains the Gunicorn startup command and `requirements.txt` lists the app dependencies. Add and commit these files before deploying; Heroku only builds files included in the commit you push:

   ```powershell
   git add app.py Procfile requirements.txt README.md test_app.py
   git commit -m "Prepare app for Heroku deployment"
   git push heroku HEAD:main
   ```

4. Open the deployed app and check its logs if needed:

   ```powershell
   heroku open -a your-unique-app-name
   heroku logs --tail -a your-unique-app-name
   ```

Heroku installs Flask and Gunicorn from `requirements.txt`, then starts the web service using the `Procfile`. Gunicorn binds to Heroku's `PORT` environment variable. **SQLite data on Heroku is not durable:** dynos have an ephemeral filesystem, so the database file can be lost when a dyno restarts, is replaced, or a new release is deployed. The `/tmp` path is writable, but does not make data persistent. This deployment is suitable for a demo only; keeping todo items reliably on Heroku requires moving the database to persistent external storage, such as Heroku Postgres, and adapting the app to use it.

## Run tests

```powershell
python -m unittest
```
