#!/usr/bin/env python3
# encoding=utf-8

# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "openweather-wrapper>=0.1.1,<0.2",
#     "prometheus-client>=0.22,<0.23",
#     "pyyaml>=6.0.2,<7.0",
#     "aiohttp>=3.11.11,<4.0",
#     "requests>=2.32.3",
#     "requests-cache>=1.2.1",
#     "matplotlib>=3.10.0"
# ]
# ///

import argparse
import logging
import signal
from os import getenv
from pathlib import Path
from time import sleep
from typing import Dict

import yaml
from openweather.weather import OpenWeather
from prometheus_client import start_http_server, Gauge


def parse_config(_config_file=None) -> Dict | None:
    if _config_file is None:
        _config_file = Path("config.yaml")

    try:
        with open(_config_file, "r") as file:
            _config = yaml.safe_load(file)
    except FileNotFoundError:
        log.error("Config file does not exist.")
    except yaml.YAMLError as _error:
        if hasattr(_error, "problem_mark"):
            mark = _error.problem_mark
            log.error("Error in configuration")
            log.error(f"Error position: ({mark.line + 1}:{mark.column + 1})")
    else:
        return _config


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", dest="config_file", type=str, nargs=1, required=False)
    parser.add_argument("-v", "--verbose", dest="verbosity", action="count", default=0)

    return parser.parse_args()


def set_logging_level(_verbosity, _level, _logger=None):
    _switcher = {
        1: "WARNING",
        2: "INFO",
        3: "DEBUG",
    }
    if _verbosity > 0:
        _level = _switcher.get(_verbosity)

    _fmt = logging.Formatter(
        "%(asctime)s - %(module)s:%(lineno)d - %(levelname)s:%(message)s", datefmt="%d.%m.%Y %H:%M:%S"
    )

    # Logger
    if _logger is None:
        _logger = logging.getLogger(__name__)

    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)

    _logger.addHandler(_ch)
    _logger.setLevel(_level)
    _logger.info(f"Setting loglevel to {_level}.")

    return _logger


def shutdown(_signal):
    global running
    running = False


if __name__ == "__main__":
    running = True
    args = parse_args()
    config = parse_config(args.config_file)

    if getenv("TERM", None):
        # noinspection PyTypeChecker
        signal.signal(signal.SIGTERM, shutdown)
        # noinspection PyTypeChecker
        signal.signal(signal.SIGINT, shutdown)

    interval = int(config.get("interval", 600))  # interval in seconds; default are 10 Minutes
    loglevel = config.get("loglevel", "INFO")  # set loglevel by Name
    listen_port = config.get("listen_port", 9126)

    api_key = config.get("api_key", None)
    units = config.get("units", "C")
    locations = config.get("locations", [])

    # Environment Variables takes precedence over config if set, except for locations
    interval = int(getenv("INTERVAL", interval))
    loglevel = getenv("LOGLEVEL", loglevel)
    listen_port = getenv("LISTEN_PORT", listen_port)

    api_key = getenv("API_KEY", api_key)
    units = getenv("UNITS", units)

    # set logging level
    log = set_logging_level(args.verbosity, loglevel)

    TEMPERATURE = Gauge("owm_temperature", "The current Temperature", ["city", "country"])
    TEMPERATURE_MIN = Gauge(
        "owm_temperature_min",
        "Minimum temperature at the moment (within large megalopolises and urban areas)",
        ["city", "country"],
    )
    TEMPERATURE_MAX = Gauge(
        "owm_temperature_max",
        "Maximum temperature at the moment (within large megalopolises and urban areas).",
        ["city", "country"],
    )
    TEMPERATURE_FEEL = Gauge(
        "owm_temperature_feel",
        "Temperature. This temperature parameter accounts for the human perception of weather.",
        ["city", "country"],
    )
    HUMIDITY = Gauge("owm_humidity", "Humidity, %", ["city", "country"])
    PRESSURE = Gauge("owm_pressure", "Atmospheric pressure on the sea level, hPa", ["city", "country"])
    WIND_DIRECTION = Gauge("owm_wind_direction", "Wind direction, degrees (meteorological)", ["city", "country"])
    WIND_SPEED = Gauge("owm_wind_speed", "Wind Speed", ["city", "country"])
    CLOUDINESS = Gauge("owm_cloudiness", "Cloudiness, %", ["city", "country"])
    SUNRISE_TIME = Gauge("owm_sunrise_time", "Sunrise Time", ["city", "country"])
    SUNSET_TIME = Gauge("owm_sunset_time", "Sunset Time", ["city", "country"])
    WEATHER_CONDITION = Gauge("owm_weather_condition", "Weather Condition", ["city", "country", "condition"])

    start_http_server(listen_port)
    log.info("Exporter ready...")
    while running:
        try:
            weather_api = OpenWeather(api_key)

            if not len(locations) > 0:
                raise Exception("No locations specified.")

            for location in locations:
                city = location.get("name")

                if location.get("lat") and location.get("lon"):
                    lat = location.get("lat")
                    lon = location.get("lon")
                    data = weather_api.get_weather(lat=lat, lon=lon)
                else:
                    data = weather_api.get_weather(city=city)

                main_data = data.get("main")
                humidity = main_data.get("humidity")
                pressure = main_data.get("pressure")

                if units != "K":
                    current_temperature = weather_api.convert_temperature(main_data.get("temp"), to_unit=units)
                    max_temperature = weather_api.convert_temperature(main_data.get("temp_max"), to_unit=units)
                    min_temperature = weather_api.convert_temperature(main_data.get("temp_min"), to_unit=units)
                    felt_temperature = weather_api.convert_temperature(main_data.get("feels_like"), to_unit=units)
                else:
                    current_temperature = main_data.get("temp")
                    max_temperature = main_data.get("temp_max")
                    min_temperature = main_data.get("temp_min")
                    felt_temperature = main_data.get("feels_like")

                sys_data = data.get("sys")
                country = sys_data.get("country")
                sunset = sys_data.get("sunset")
                sunrise = sys_data.get("sunrise")

                wind_data = data.get("wind")
                wind_direction = wind_data.get("deg")
                wind_speed = wind_data.get("speed")

                cloudiness = data.get("clouds").get("all")
                weather_condition = data.get("weather")[0].get("description")

                TEMPERATURE.labels(city, country).set(current_temperature)
                TEMPERATURE_MIN.labels(city, country).set(min_temperature)
                TEMPERATURE_MAX.labels(city, country).set(max_temperature)
                TEMPERATURE_FEEL.labels(city, country).set(felt_temperature)
                HUMIDITY.labels(city, country).set(humidity)
                PRESSURE.labels(city, country).set(pressure)
                WIND_DIRECTION.labels(city, country).set(wind_direction)
                WIND_SPEED.labels(city, country).set(wind_speed)
                CLOUDINESS.labels(city, country).set(cloudiness)
                SUNRISE_TIME.labels(city, country).set(sunrise)
                SUNSET_TIME.labels(city, country).set(sunset)
                WEATHER_CONDITION.labels(city, country, weather_condition).set(1)
        except Exception as error:
            log.error(error)
            pass
        finally:
            sleep(interval)
