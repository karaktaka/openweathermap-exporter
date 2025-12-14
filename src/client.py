#!/usr/bin/env python3
# encoding=utf-8

import argparse
import logging
import signal
from enum import Enum
from os import getenv
from pathlib import Path
from time import sleep
from typing import Dict, List

import yaml
from openweather.weather import OpenWeather
from prometheus_client import Gauge, start_http_server

# Prometheus metrics
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
WIND_DIRECTION = Gauge(
    "owm_wind_direction",
    "Wind direction, degrees (meteorological)",
    ["city", "country"],
)
WIND_SPEED = Gauge("owm_wind_speed", "Wind Speed", ["city", "country"])
CLOUDINESS = Gauge("owm_cloudiness", "Cloudiness, %", ["city", "country"])
SUNRISE_TIME = Gauge("owm_sunrise_time", "Sunrise Time", ["city", "country"])
SUNSET_TIME = Gauge("owm_sunset_time", "Sunset Time", ["city", "country"])
WEATHER_CONDITION = Gauge("owm_weather_condition", "Weather Condition", ["city", "country", "condition"])


class VerbosityLevel(Enum):
    NOTSET = 0
    WARNING = 1
    INFO = 2
    DEBUG = 3


def parse_config(_config_file: str = None) -> Dict:
    """Parse the YAML configuration file.

    Args:
        _config_file: Path to the configuration file. If None, uses default 'config.yaml'.

    Returns:
        Dict containing the configuration.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the YAML file is invalid.
    """
    if _config_file is None:
        _config_file = Path(__file__).parent / "config.yaml"
    try:
        with open(_config_file, "r", encoding="utf-8") as _f:
            _config = yaml.safe_load(_f)
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as _error:
        if hasattr(_error, "problem_mark"):
            mark = _error.problem_mark
            print("Error in configuration. Please check your configuration file for syntax errors.")
            print(f"Error in configuration at position: ({mark.line + 1}:{mark.column + 1})")
        exit(1)
    else:
        return _config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Namespace containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(description="OpenWeatherMap Prometheus Exporter")
    parser.add_argument("-c", "--config-file", dest="config_file", type=str, help="Path to config file")
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbosity",
        action="count",
        default=0,
        help="Increase verbosity (can be used multiple times)",
    )

    return parser.parse_args()


def configure_logging(_logger: logging.Logger, _level: str = "INFO") -> logging.Logger:
    """Configure logging level and format.

    Args:
        _logger: Existing logger instance
        _level: Logging level from configuration

    Returns:
        Configured logger instance
    """
    if not _logger.handlers:
        _fmt = logging.Formatter(
            "%(asctime)s - %(module)s:%(lineno)d - %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        _ch = logging.StreamHandler()
        _ch.setFormatter(_fmt)

        _logger.addHandler(_ch)
        _logger.setLevel(_level)
        _logger.info(f"Setting loglevel to {_level}")

    return _logger


def shutdown(_signal):
    """Signal handler to gracefully shut down the application."""
    global RUNNING
    RUNNING = False


def main(_api: OpenWeather, _locations: List[Dict[str, any]], _log: logging.Logger):
    _data = {}
    while RUNNING:
        try:
            for _location in _locations:
                _city = _location.get("name")
                if not _city:
                    _log.warning(f"Skipping location without name: {_location}")
                    continue

                try:
                    # Fetch weather data
                    if _location.get("lat") is not None and _location.get("lon") is not None:
                        _data = _api.get_weather(lat=_location["lat"], lon=_location["lon"])
                    else:
                        _data = _api.get_weather(city=_city)

                    # Extract and validate main weather data
                    _main_data = _data.get("main", {})
                    _sys_data = _data.get("sys", {})
                    _wind_data = _data.get("wind", {})
                    _clouds_data = _data.get("clouds", {})
                    _weather_data = _data.get("weather", [{}])[0]

                    # Process temperature data
                    if _units != "K":
                        _current_temperature = _api.convert_temperature(_main_data.get("temp"), to_unit=_units)
                        _max_temperature = _api.convert_temperature(_main_data.get("temp_max"), to_unit=_units)
                        _min_temperature = _api.convert_temperature(_main_data.get("temp_min"), to_unit=_units)
                        _felt_temperature = _api.convert_temperature(_main_data.get("feels_like"), to_unit=_units)
                    else:
                        _current_temperature = _main_data.get("temp")
                        _max_temperature = _main_data.get("temp_max")
                        _min_temperature = _main_data.get("temp_min")
                        _felt_temperature = _main_data.get("feels_like")

                    # Update metrics
                    _country = _sys_data.get("country", "unknown")

                    TEMPERATURE.labels(_city, _country).set(_current_temperature)
                    TEMPERATURE_MIN.labels(_city, _country).set(_min_temperature)
                    TEMPERATURE_MAX.labels(_city, _country).set(_max_temperature)
                    TEMPERATURE_FEEL.labels(_city, _country).set(_felt_temperature)
                    HUMIDITY.labels(_city, _country).set(_main_data.get("humidity", 0))
                    PRESSURE.labels(_city, _country).set(_main_data.get("pressure", 0))
                    WIND_DIRECTION.labels(_city, _country).set(_wind_data.get("deg", 0))
                    WIND_SPEED.labels(_city, _country).set(_wind_data.get("speed", 0))
                    CLOUDINESS.labels(_city, _country).set(_clouds_data.get("all", 0))
                    SUNRISE_TIME.labels(_city, _country).set(_sys_data.get("sunrise", 0))
                    SUNSET_TIME.labels(_city, _country).set(_sys_data.get("sunset", 0))
                    WEATHER_CONDITION.labels(_city, _country, _weather_data.get("description", "unknown")).set(1)

                    _log.debug(f"Updated metrics for {_city}, {_country}")
                    _log.debug(_data)
                except Exception as _loc_error:
                    _log.error(f"Error processing location {_city}: {_loc_error}")
                    _log.debug(_data)
                    continue

        except Exception as _error:
            _log.error(f"Error in main loop: {_error}")
        finally:
            sleep(interval)


if __name__ == "__main__":
    RUNNING = True
    api_key = None
    args = parse_args()
    config = parse_config(args.config_file)

    try:
        if getenv("TERM", None):
            # noinspection PyTypeChecker
            signal.signal(signal.SIGTERM, shutdown)
            # noinspection PyTypeChecker
            signal.signal(signal.SIGINT, shutdown)

        # Configuration with defaults and environment overrides
        interval: int = int(getenv("INTERVAL", config.get("interval", "600")))
        log_level: str = getenv(
            "LOGLEVEL", VerbosityLevel(args.verbosity).name if args.verbosity > 0 else config.get("loglevel", "INFO")
        )
        listen_port: int = int(getenv("LISTEN_PORT", config.get("listen_port", "9126")))
        api_key: str | None = getenv("API_KEY", config.get("api_key"))
        _units: str = getenv("UNITS", config.get("units", "C"))
        locations: list = config.get("locations", [])

        if not api_key:
            raise ValueError("API key is required")
        if not locations:
            raise ValueError("No locations specified in configuration")

        # Initialize logging
        logger = logging.getLogger(__name__)
        log = configure_logging(logger, log_level)

        start_http_server(listen_port)
        log.info(f"Exporter started on port {listen_port}")

        api = OpenWeather(api_key)

        main(api, locations, log)

    except KeyboardInterrupt:
        print("Received interrupt signal, shutting down...")
    except Exception as error:
        print(f"Fatal error: {error}")
        raise
    finally:
        RUNNING = False
