import json
import os
import pandas as pd
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from .db import get_db
from .tasks import fetch_forecast, run_weather_job

bp = Blueprint("weather", __name__)

def query_dataframe(query, params=()):
    with get_db().cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [desc.name for desc in cur.description]
    return pd.DataFrame(rows, columns=columns)

def location_options():
    try:
        with open(current_app.config["LOCATIONS_FILE"], encoding="utf-8") as f:
            data = json.load(f)
        return [{"name": name, "latitude": coords[0], "longitude": coords[1]} for name, coords in data.items()]
    except (FileNotFoundError, json.JSONDecodeError, TypeError, IndexError):
        return []

@bp.route("/")
@bp.route("/weather")
def weather():
    current_location = current_app.config.get("CURRENT_LOCATION", "").strip()
    row = query_dataframe(
        """SELECT created_at AS "Time", location AS "Location", description AS "Description",
                  temperature AS "Temperature", pressure AS "Pressure",
                  feelslike AS "Feels Like", humidity AS "Humidity", dew_point AS "Dew Point",
                  winddirection AS "Wind Direction", windspeed AS "Wind Speed",
                  sunrise AS "Sunrise", sunset AS "Sunset", clouds AS "Clouds"
           FROM chart
           WHERE location = %s
           ORDER BY created_at DESC
           LIMIT 1""",
        (current_location,),
    )
    record = row.iloc[0].to_dict() if not row.empty else None
    return render_template(
        "weather.html",
        record=record,
        current_location=current_location,
    )


@bp.route("/forecast")
def forecast():
    current_location = current_app.config.get("CURRENT_LOCATION", "").strip()
    forecast_data = fetch_forecast(current_location)
    return render_template(
        "forecast.html",
        forecast=forecast_data,
        current_location=current_location,
    )


@bp.route("/historical")
def historical():
    selected_city = request.args.get("city", "").strip()
    query = """SELECT created_at AS "Time", location AS "Location", description AS "Description",
               temperature AS "Temperature (°F)", pressure AS "Barometer",
               feelslike AS "Feels Like", humidity AS "Humidity", dew_point AS "Dew Point",
               winddirection AS "Wind Direction", windspeed AS "Wind Speed",
               sunrise AS "Sunrise", sunset AS "Sunset" FROM chart"""
    params = ()
    if selected_city:
        query += " WHERE location = %s"
        params = (selected_city,)
    query += " ORDER BY created_at DESC"
    df = query_dataframe(query, params)
    cities = query_dataframe(
        "SELECT DISTINCT location FROM weather_jobs WHERE location IS NOT NULL ORDER BY location"
    )["location"].tolist()
    if not df.empty:
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    table = df.fillna("").to_html(
        classes="table table-striped table-bordered table-hover",
        index=False,
        escape=True,
    ) if not df.empty else ""
    return render_template(
        "historical.html",
        table=table,
        cities=cities,
        selected_city=selected_city,
        current_location=current_app.config.get("CURRENT_LOCATION", ""),
    )

@bp.route("/control", methods=("GET", "POST"))
def control():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            db.execute("DELETE FROM weather_jobs WHERE id = %s", (request.form["job_id"],))
            db.commit()
            flash("Weather job removed.", "success")
            return redirect(url_for("weather.control"))
        if action == "toggle":
            db.execute("UPDATE weather_jobs SET enabled = NOT enabled, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (request.form["job_id"],))
            db.commit()
            return redirect(url_for("weather.control"))
        if action == "run":
            job_id = int(request.form["job_id"])
            success = run_weather_job(job_id)
            flash("Weather job completed." if success else "Weather job failed. Check the job status.", "success" if success else "error")
            return redirect(url_for("weather.control"))
        try:
            name = request.form["name"].strip()
            location = request.form["location"].strip()
            latitude = float(request.form["latitude"])
            longitude = float(request.form["longitude"])
            interval_minutes = int(request.form["interval_minutes"])
            if not name or not location:
                raise ValueError("Name and location are required.")
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("Latitude/longitude are out of range.")
            if interval_minutes not in {15, 60, 240, 1440}:
                raise ValueError("Invalid collection interval.")
            job_id = request.form.get("job_id")
            if job_id:
                db.execute("""UPDATE weather_jobs SET name=%s, location=%s, latitude=%s, longitude=%s,
                           interval_minutes=%s, enabled=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
                           (name, location, latitude, longitude, interval_minutes, bool(request.form.get("enabled")), job_id))
            else:
                db.execute("""INSERT INTO weather_jobs (name, location, latitude, longitude, interval_minutes, enabled)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                           (name, location, latitude, longitude, interval_minutes, bool(request.form.get("enabled", "1"))))
            db.commit()
            flash("Weather job saved.", "success")
        except (KeyError, ValueError) as exc:
            flash(str(exc) or "Invalid weather job settings.", "error")
        return redirect(url_for("weather.control"))
    jobs = db.execute("SELECT * FROM weather_jobs ORDER BY enabled DESC, name").fetchall()
    return render_template("control.html", jobs=jobs, locations=location_options())

@bp.route("/api/location-search")
def location_search():
    query = request.args.get("q", "").strip().lower()
    if len(query) < 2:
        return jsonify({"locations": []})
    matches = []
    for item in location_options():
        name = item["name"].lower()
        if query in name:
            score = 0 if name.startswith(query) else (1 if f", {query}" in name else 2)
            matches.append((score, len(name), item))
    matches.sort(key=lambda x: (x[0], x[1], x[2]["name"].lower()))
    return jsonify({"locations": [item for _, _, item in matches[:12]]})

@bp.route("/api/latest-temp")
def latest_temp():
    row = get_db().execute("SELECT temperature FROM chart WHERE location = %s ORDER BY created_at DESC LIMIT 1", (current_app.config.get("CURRENT_LOCATION", ""),)).fetchone()
    return jsonify({"temperature": f"{row['temperature']}°" if row and row["temperature"] is not None else "N/A"})

@bp.route("/api/latest-humidity")
def latest_humidity():
    row = get_db().execute("SELECT humidity FROM chart WHERE location = %s ORDER BY created_at DESC LIMIT 1", (current_app.config.get("CURRENT_LOCATION", ""),)).fetchone()
    return jsonify({"humidity": row["humidity"] if row and row["humidity"] is not None else "N/A"})

@bp.route("/api/latest-windspeed")
def latest_windspeed():
    row = get_db().execute("SELECT windspeed FROM chart WHERE location = %s ORDER BY created_at DESC LIMIT 1", (current_app.config.get("CURRENT_LOCATION", ""),)).fetchone()
    return jsonify({"windspeed": row["windspeed"] if row and row["windspeed"] is not None else "N/A"})

@bp.route("/api/latest-wind-direction")
def latest_wind_direction():
    row = get_db().execute("SELECT winddirection FROM chart WHERE location = %s ORDER BY created_at DESC LIMIT 1", (current_app.config.get("CURRENT_LOCATION", ""),)).fetchone()
    return jsonify({"wind_degrees": row["winddirection"] if row else None})

@bp.route("/api/current-location")
def current_location():
    return jsonify({"location": current_app.config.get("CURRENT_LOCATION") or "Unknown Location"})

@bp.context_processor
def navigation_context():
    return {"hostname": os.uname().nodename}
