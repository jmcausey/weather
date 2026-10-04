#!/usr/bin/env python3
import time
from weather.tasks import run_due_weather_jobs

if __name__ == "__main__":
    print("Starting weather scheduler")
    while True:
        results = run_due_weather_jobs()
        if results:
            print(f"Ran weather jobs: {results}")
        time.sleep(30)
