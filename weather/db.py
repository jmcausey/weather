import sqlite3
from flask import current_app, g


def get_db():
    if "db" not in g:
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        g.db = db
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS chart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            location TEXT NOT NULL,
            geolocation TEXT,
            description TEXT,
            temperature REAL,
            pressure INTEGER,
            feelslike REAL,
            humidity INTEGER,
            visibility INTEGER,
            windspeed REAL,
            winddirection INTEGER,
            clouds INTEGER,
            sunrise DATETIME,
            sunset DATETIME,
            dew_point REAL
        );
        CREATE INDEX IF NOT EXISTS idx_chart_location_created
            ON chart(location, created_at DESC);
        """)
        db.commit()
