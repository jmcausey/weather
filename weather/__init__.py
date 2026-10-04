import os
import sqlite3
from pathlib import Path

from flask import Flask, g, current_app


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True, template_folder="../templates", static_folder="../static")
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    database = os.environ.get("WEATHER_DATABASE", str(Path(app.instance_path) / "weather.sqlite"))
    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "weather-local"),
        DATABASE=database,
        CURRENT_LOCATION=os.environ.get("CURRENT_LOCATION", ""),
        LOCATIONS_FILE=os.environ.get("LOCATIONS_FILE", str(Path(app.root_path).parent / "locations.json")),
        OPENWEATHER_API_KEY=os.environ.get("OPENWEATHER_API_KEY", ""),
    )
    if test_config:
        app.config.update(test_config)
    from .db import init_db
    init_db(app)
    from .routes import bp
    app.register_blueprint(bp)
    return app


def get_db():
    if "db" not in g:
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        g.db = db
    return g.db
