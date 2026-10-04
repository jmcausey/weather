import os
import pandas as pd
from flask import Blueprint, current_app, jsonify, render_template, request
from .db import get_db

bp = Blueprint("weather", __name__)


@bp.route("/")
@bp.route("/weather")
def weather():
    selected_city = request.args.get("city", "").strip()
    current_location = current_app.config.get("CURRENT_LOCATION", "").strip()
    db = get_db()
    query = """
        SELECT created_at AS Time, location AS Location,
               description AS Description,
               temperature AS [Temperature (°F)],
               pressure AS Barometer, feelslike AS [Feels Like],
               humidity AS Humidity, dew_point AS [Dew Point],
               winddirection AS [Wind Direction],
               windspeed AS [Wind Speed], sunrise AS Sunrise, sunset AS Sunset
        FROM chart
    """
    if selected_city:
        query += " WHERE location = ?"
        params = (selected_city,)
    elif current_location:
        query += " WHERE location = ?"
        params = (current_location,)
    else:
        params = ()
    query += " ORDER BY created_at DESC"
    df = pd.read_sql_query(query, db, params=params)
    cities = pd.read_sql_query(
        "SELECT DISTINCT location FROM chart WHERE location IS NOT NULL ORDER BY location", db
    )["location"].tolist()
    if not df.empty:
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    table = df.fillna("").to_html(
        classes="table table-striped table-bordered table-hover",
        index=False, escape=True
    ) if not df.empty else ""
    return render_template("weather.html", table=table, cities=cities, selected_city=selected_city)


@bp.route("/api/latest-temp")
def latest_temp():
    row = get_db().execute(
        "SELECT temperature FROM chart WHERE location = ? ORDER BY created_at DESC LIMIT 1",
        (current_app.config.get("CURRENT_LOCATION", ""),)
    ).fetchone()
    return jsonify({"temperature": f"{row['temperature']}°" if row and row["temperature"] is not None else "N/A"})


@bp.route("/api/latest-humidity")
def latest_humidity():
    row = get_db().execute(
        "SELECT humidity FROM chart WHERE location = ? ORDER BY created_at DESC LIMIT 1",
        (current_app.config.get("CURRENT_LOCATION", ""),)
    ).fetchone()
    return jsonify({"humidity": row["humidity"] if row and row["humidity"] is not None else "N/A"})


@bp.route("/api/latest-windspeed")
def latest_windspeed():
    row = get_db().execute(
        "SELECT windspeed FROM chart WHERE location = ? ORDER BY created_at DESC LIMIT 1",
        (current_app.config.get("CURRENT_LOCATION", ""),)
    ).fetchone()
    return jsonify({"windspeed": row["windspeed"] if row and row["windspeed"] is not None else "N/A"})


@bp.route("/api/latest-wind-direction")
def latest_wind_direction():
    row = get_db().execute(
        "SELECT winddirection FROM chart WHERE location = ? ORDER BY created_at DESC LIMIT 1",
        (current_app.config.get("CURRENT_LOCATION", ""),)
    ).fetchone()
    return jsonify({"wind_degrees": row["winddirection"] if row else None})


@bp.route("/api/current-location")
def current_location():
    return jsonify({"location": current_app.config.get("CURRENT_LOCATION") or "Unknown Location"})


@bp.context_processor
def navigation_context():
    return {"hostname": os.uname().nodename}
