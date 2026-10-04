import json, math, os, time
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

def load_locations() -> Dict[str, Tuple[float, float]]:
    try:
        with open(LOCATIONS_FILE, encoding="utf-8") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Failed to load locations file: {exc}"); return {}

def get_location_coordinates(query):
    for name, coords in load_locations().items():
        if query.lower() in name.lower(): return coords[0], coords[1]
    return None, None

def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def get_weather_data_from_api(city_name=None):
    city_name = city_name or CURRENT_LOCATION
    if not city_name or not OPENWEATHER_API_KEY: return None
    lat, lon = get_location_coordinates(city_name)
    if lat is None or lon is None:
        print(f"No coordinates found for {city_name}")
        return None
    try:
        r = requests.get(OPENWEATHER_BASE_URL, params={"lat":lat,"lon":lon,"appid":OPENWEATHER_API_KEY,"units":"imperial"}, timeout=10)
        r.raise_for_status(); return r.json()
    except requests.RequestException as exc:
        print(f"Error fetching weather data: {exc}"); return None

def process_and_insert_weather_data(api_data):
    if not api_data: return False
    try:
        coord=api_data.get("coord",{}); weather=api_data.get("weather",[{}]); main=api_data.get("main",{}); wind=api_data.get("wind",{}); system=api_data.get("sys",{})
        temp=main.get("temp"); humidity=main.get("humidity")
        dew=None
        if temp is not None and humidity:
            vapor=math.log(humidity/100)+(17.27*temp)/(temp+237.3)
            dew=round((237.3*vapor)/(17.27-vapor))
        def local_time(v): return datetime.fromtimestamp(v).strftime("%Y-%m-%d %H:%M:%S") if v else None
        data={"location":api_data.get("name"),"geolocation":f"{coord['lat']},{coord['lon']}" if "lat" in coord and "lon" in coord else None,
              "description":weather[0].get("description") if weather else None,"temperature":temp,"pressure":main.get("pressure"),
              "feelslike":main.get("feels_like"),"humidity":humidity,"visibility":api_data.get("visibility"),
              "windspeed":wind.get("speed"),"winddirection":wind.get("deg"),"clouds":api_data.get("clouds",{}).get("all"),
              "sunrise":local_time(system.get("sunrise")),"sunset":local_time(system.get("sunset")),"dew_point":dew}
        with get_db_connection() as conn:
            conn.execute("""INSERT INTO chart (location,geolocation,description,temperature,pressure,feelslike,humidity,visibility,windspeed,winddirection,clouds,sunrise,sunset,dew_point)
              VALUES (%(location)s,%(geolocation)s,%(description)s,%(temperature)s,%(pressure)s,%(feelslike)s,%(humidity)s,%(visibility)s,%(windspeed)s,%(winddirection)s,%(clouds)s,%(sunrise)s,%(sunset)s,%(dew_point)s)""", data)
        print(f"Successfully recorded weather for {data['location']}."); return True
    except Exception as exc:
        print(f"Error processing or inserting data: {exc}"); return False

def graph1(database_url=DATABASE_URL, location_name=CURRENT_LOCATION, output_filename=None):
    if not output_filename:
        output_dir=os.path.expanduser("~/local/data/graphs"); os.makedirs(output_dir,exist_ok=True)
        output_filename=os.path.join(output_dir,f"mpl_stackplot_{int(time.time())}.png")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT created_at,temperature,humidity FROM chart WHERE location=%s ORDER BY created_at ASC",(location_name,))
            rows=cur.fetchall()
    df=pd.DataFrame(rows, columns=["created_at","temperature","humidity"])
    if df.empty: return None
    df["created_at"]=pd.to_datetime(df["created_at"]); df.set_index("created_at",inplace=True)
    fig,ax=plt.subplots(figsize=(12,6)); ax.stackplot(df.index,df["temperature"],df["humidity"],labels=["Temperature","Humidity (%)"],alpha=.6)
    ax.set_xlabel("Time (Hourly)"); ax.set_ylabel("Stacked Values"); ax.grid(True,linestyle="--",alpha=.4)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    plt.setp(ax.get_xticklabels(),rotation=45,ha="right"); ax.legend(loc="upper left"); plt.title(f"Hourly Weather Stackplot - {location_name}")
    plt.tight_layout(); plt.savefig(output_filename,dpi=300); plt.close(fig); return os.path.basename(output_filename)

def fetch_weather(city_name=None):
    data=get_weather_data_from_api(city_name)
    return process_and_insert_weather_data(data) if data else False

if __name__=="__main__": fetch_weather()
