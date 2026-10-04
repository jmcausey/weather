import psycopg
from psycopg.rows import dict_row
from flask import current_app, g

def get_db():
    if "db" not in g:
        g.db = psycopg.connect(current_app.config["DATABASE_URL"], row_factory=dict_row)
    return g.db

def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chart (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    location TEXT NOT NULL,
                    geolocation TEXT,
                    description TEXT,
                    temperature DOUBLE PRECISION,
                    pressure INTEGER,
                    feelslike DOUBLE PRECISION,
                    humidity INTEGER,
                    visibility INTEGER,
                    windspeed DOUBLE PRECISION,
                    winddirection INTEGER,
                    clouds INTEGER,
                    sunrise TIMESTAMP,
                    sunset TIMESTAMP,
                    dew_point DOUBLE PRECISION
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chart_location_created
                ON chart(location, created_at DESC);
            """)
        db.commit()
