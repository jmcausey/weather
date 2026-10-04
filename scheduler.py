#!/usr/bin/env python3
import time
from weather.tasks import fetch_weather
if __name__=="__main__":
    print("Starting weather scheduler")
    while True:
        fetch_weather()
        time.sleep(3600)
