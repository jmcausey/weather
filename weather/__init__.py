import os
from pathlib import Path
from flask import Flask

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True, template_folder="../templates", static_folder="../static")
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "weather-local"),
        DATABASE_URL=os.environ.get("DATABASE_URL", "postgresql://cl:change-me@localhost:5432/cl"),
        CURRENT_LOCATION=os.environ.get("CURRENT_LOCATION", ""),
        LOCATIONS_FILE=os.environ.get("LOCATIONS_FILE", str(Path(app.root_path).parent / "data" / "locations" / "locations.json")),
        OPENWEATHER_API_KEY=os.environ.get("OPENWEATHER_API_KEY", ""),
    )
    if test_config:
        app.config.update(test_config)
    from .db import init_db
    init_db(app)
    from .routes import bp
    app.register_blueprint(bp)
    return app
