# Weather

Standalone Flask weather service migrated from `jmcausey/localservices`.

The Docker deployment is designed to run alongside `jmcausey/cl` and use the same PostgreSQL server/database. Weather owns the `chart` table; CL owns its Craigslist tables.

## Docker

Start CL first so its PostgreSQL container and shared Docker network exist:

    cd ~/dev/jmcausey/cl
    docker compose up -d --build

Copy `.env.example` to `.env` and set your OpenWeather key and the same PostgreSQL credentials used by CL.

Then start weather:

    cd ~/dev/jmcausey/weather
    docker compose up -d --build

Weather listens on `http://localhost:5002`.

The weather containers connect to CL's PostgreSQL service using:

    postgresql://cl:PASSWORD@postgres:5432/cl

The `postgres` hostname works because both Compose projects join the external `cl_shared_data` network. Weather does not start a second PostgreSQL container.

## Features

- OpenWeather current-condition collection
- PostgreSQL weather history
- Location filtering and historical weather table
- JSON endpoints for temperature, humidity, wind speed, wind direction, and location
- Local Services three-row navigation bar with live weather badges and clock
- Hourly weather collection
- Temperature/humidity history graph generation

## Configuration

    OPENWEATHER_API_KEY=
    CURRENT_LOCATION=Athens,TX
    DATABASE_URL=postgresql://cl:change-me@postgres:5432/cl
    LOCATIONS_FILE=/app/data/locations/locations.json
    FLASK_SECRET_KEY=change-this-secret
    APP_PORT=5002

## Manual run

For non-Docker development, set `DATABASE_URL` to a reachable PostgreSQL instance, install requirements, and run:

    flask --app app run --port 5002

Collect weather once:

    python -m weather.tasks

Run the hourly collector:

    python scheduler.py
