# Weather

Standalone Flask weather service migrated from jmcausey/localservices.

## Features

- OpenWeather current-condition collection
- SQLite weather history
- Location filtering and historical weather table
- JSON endpoints for temperature, humidity, wind speed, wind direction, and location
- The Local Services three-row navigation bar, including live weather badges and clock
- Hourly weather collection
- Temperature/humidity history graph generation

## Configuration

Set OPENWEATHER_API_KEY, CURRENT_LOCATION, WEATHER_DATABASE, and LOCATIONS_FILE.

The location file is expected to be the same locations.json data used by the original Local Services weather collector.

## Run

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENWEATHER_API_KEY=your-key
export CURRENT_LOCATION="Athens,TX"
flask --app app run --port 5001

Collect weather once with: python -m weather.tasks

Run the hourly collector with: python scheduler.py
