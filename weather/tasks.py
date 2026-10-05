import json
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import psycopg
import requests
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://cl:change-me@localhost:5432/cl")
LOCATIONS_FILE = os.path.expanduser(os.environ.get("LOCATIONS_FILE", str(Path(__file__).resolve().parent.parent / "data" / "locations" / "locations.json")))
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
CURRENT_LOCATION = os.environ.get("CURRENT_LOCATION")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def fetch_forecast(location_name=None):
    """Fetch and normalize the OpenWeather 5-day / 3-hour forecast."""
    location_name = location_name or CURRENT_LOCATION
    if not OPENWEATHER_API_KEY or not location_name:
        return None

    latitude, longitude = get_location_coordinates(location_name)
    if latitude is None or longitude is None:
        print(f"No coordinates found for forecast location {location_name}")
        return None

    try:
        response = requests.get(
            OPENWEATHER_FORECAST_URL,
            params={
                "lat": latitude,
                "lon": longitude,
                "appid": OPENWEATHER_API_KEY,
                "units": "imperial",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        print(f"Error fetching forecast: {exc}")
        return None

    city = payload.get("city", {})
    timezone_offset = city.get("timezone", 0)
    points = []
    for item in payload.get("list", []):
        timestamp = datetime.utcfromtimestamp(item["dt"])
        local_timestamp = timestamp + pd.Timedelta(seconds=timezone_offset)
        weather = (item.get("weather") or [{}])[0]
        main = item.get("main", {})
        wind = item.get("wind", {})
        points.append({
            "time": local_timestamp.strftime("%a %b %-d, %-I:%M %p"),
            "day": local_timestamp.strftime("%A"),
            "date": local_timestamp.strftime("%Y-%m-%d"),
            "temp": round(main["temp"]),
            "feels_like": round(main["feels_like"]),
            "description": weather.get("description", "").title(),
            "icon": weather.get("icon"),
            "pop": round((item.get("pop") or 0) * 100),
            "humidity": main.get("humidity"),
            "wind_speed": round(wind.get("speed", 0)),
            "wind_deg": wind.get("deg"),
            "clouds": item.get("clouds", {}).get("all"),
        })

    return {
        "location": location_name,
        "city": city.get("name") or location_name,
        "country": city.get("country"),
        "points": points,
    }


def load_locations() -> Dict[str, Tuple[float, float]]:
    try:
        with open(LOCATIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Failed to load locations file: {exc}")
        return {}


def get_location_coordinates(query):
    for name, coords in load_locations().items():
        if query.lower() in name.lower():
            return coords[0], coords[1]
    return None, None


def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def get_weather_data_from_coordinates(latitude, longitude):
    if not OPENWEATHER_API_KEY:
        return None
    try:
        r = requests.get(
            OPENWEATHER_BASE_URL,
            params={
                "lat": latitude,
                "lon": longitude,
                "appid": OPENWEATHER_API_KEY,
                "units": "imperial",
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        print(f"Error fetching weather data: {exc}")
        return None


def get_weather_data_from_api(city_name=None):
    city_name = city_name or CURRENT_LOCATION
    if not city_name:
        return None
    lat, lon = get_location_coordinates(city_name)
    if lat is None or lon is None:
        print(f"No coordinates found for {city_name}")
        return None
    return get_weather_data_from_coordinates(lat, lon)


def process_and_insert_weather_data(api_data):
    if not api_data:
        return False
    try:
        coord = api_data.get("coord", {})
        weather = api_data.get("weather", [{}])
        main = api_data.get("main", {})
        wind = api_data.get("wind", {})
        system = api_data.get("sys", {})
        temp = main.get("temp")
        humidity = main.get("humidity")
        dew = None
        if temp is not None and humidity:
            vapor = math.log(humidity / 100) + (17.27 * temp) / (temp + 237.3)
            dew = round((237.3 * vapor) / (17.27 - vapor))

        def local_time(v):
            return datetime.fromtimestamp(v).strftime("%Y-%m-%d %H:%M:%S") if v else None

        data = {
            "location": api_data.get("name"),
            "geolocation": f"{coord['lat']},{coord['lon']}" if "lat" in coord and "lon" in coord else None,
            "description": weather[0].get("description") if weather else None,
            "temperature": temp,
            "pressure": main.get("pressure"),
            "feelslike": main.get("feels_like"),
            "humidity": humidity,
            "visibility": api_data.get("visibility"),
            "windspeed": wind.get("speed"),
            "winddirection": wind.get("deg"),
            "clouds": api_data.get("clouds", {}).get("all"),
            "sunrise": local_time(system.get("sunrise")),
            "sunset": local_time(system.get("sunset")),
            "dew_point": dew,
        }
        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO chart
                (location,geolocation,description,temperature,pressure,feelslike,humidity,visibility,
                 windspeed,winddirection,clouds,sunrise,sunset,dew_point)
                VALUES (%(location)s,%(geolocation)s,%(description)s,%(temperature)s,%(pressure)s,
                        %(feelslike)s,%(humidity)s,%(visibility)s,%(windspeed)s,%(winddirection)s,
                        %(clouds)s,%(sunrise)s,%(sunset)s,%(dew_point)s)""",
                data,
            )
        print(f"Successfully recorded weather for {data['location']}.")
        return True
    except Exception as exc:
        print(f"Error processing or inserting data: {exc}")
        return False


def fetch_weather_at_coordinates(latitude, longitude, display_name=None):
    api_data = get_weather_data_from_coordinates(latitude, longitude)
    if api_data and display_name:
        api_data["name"] = display_name
    return process_and_insert_weather_data(api_data)


def run_weather_job(job_id):
    with get_db_connection() as conn:
        job = conn.execute(
            "SELECT * FROM weather_jobs WHERE id = %s AND enabled = TRUE",
            (job_id,),
        ).fetchone()
    if not job:
        return False
    try:
        success = fetch_weather_at_coordinates(job["latitude"], job["longitude"], job["location"])
        with get_db_connection() as conn:
            conn.execute(
                """UPDATE weather_jobs
                   SET last_run_at = CURRENT_TIMESTAMP,
                       last_status = %s,
                       last_error = NULL,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                ("completed" if success else "failed", job_id),
            )
        return success
    except Exception as exc:
        with get_db_connection() as conn:
            conn.execute(
                """UPDATE weather_jobs
                   SET last_run_at = CURRENT_TIMESTAMP,
                       last_status = 'failed',
                       last_error = %s,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (str(exc), job_id),
            )
        return False


def due_weather_jobs():
    with get_db_connection() as conn:
        return conn.execute(
            """SELECT * FROM weather_jobs
               WHERE enabled = TRUE
                 AND (last_run_at IS NULL
                      OR last_run_at <= CURRENT_TIMESTAMP
                         - (interval_minutes * INTERVAL '1 minute'))
               ORDER BY id"""
        ).fetchall()


def run_due_weather_jobs():
    results = []
    for job in due_weather_jobs():
        results.append((job["id"], run_weather_job(job["id"])))
    return results


def graph1(database_url=DATABASE_URL, location_name=CURRENT_LOCATION, output_filename=None):
    if not output_filename:
        output_dir = os.path.expanduser("~/local/data/graphs")
        os.makedirs(output_dir, exist_ok=True)
        output_filename = os.path.join(output_dir, f"mpl_stackplot_{int(time.time())}.png")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT created_at,temperature,humidity FROM chart WHERE location=%s ORDER BY created_at ASC", (location_name,))
            rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["created_at", "temperature", "humidity"])
    if df.empty:
        return None
    df["created_at"] = pd.to_datetime(df["created_at"])
    df.set_index("created_at", inplace=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.stackplot(df.index, df["temperature"], df["humidity"], labels=["Temperature", "Humidity (%)"], alpha=.6)
    ax.set_xlabel("Time (Hourly)")
    ax.set_ylabel("Stacked Values")
    ax.grid(True, linestyle="--", alpha=.4)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.legend(loc="upper left")
    plt.title(f"Hourly Weather Stackplot - {location_name}")
    plt.tight_layout()
    plt.savefig(output_filename, dpi=300)
    plt.close(fig)
    return os.path.basename(output_filename)


def fetch_weather(city_name=None):
    data = get_weather_data_from_api(city_name)
    return process_and_insert_weather_data(data) if data else False


if __name__ == "__main__":
    fetch_weather()
