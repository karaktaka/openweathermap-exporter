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


# Global variables
running: bool = True  # Control variable for the main loop
log: logging.Logger  # Global logger instance

# Prometheus metrics
TEMPERATURE: Gauge
TEMPERATURE_MIN: Gauge
TEMPERATURE_MAX: Gauge
TEMPERATURE_FEEL: Gauge
HUMIDITY: Gauge
PRESSURE: Gauge
WIND_DIRECTION: Gauge
WIND_SPEED: Gauge
CLOUDINESS: Gauge
SUNRISE_TIME: Gauge
SUNSET_TIME: Gauge
WEATHER_CONDITION: Gauge


def parse_config(_config_file: str | Path | None = None) -> Dict:
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
        _config_file = Path("config.yaml")

    try:
        with open(_config_file, "r") as file:
            _config = yaml.safe_load(file)
            if not _config:
                raise ValueError("Configuration file is empty")
            return _config
    except FileNotFoundError:
        print("Config file does not exist.")
        raise
    except yaml.YAMLError as _error:
        if hasattr(_error, "problem_mark"):
            mark = _error.problem_mark
            print(f"Error in configuration at position: ({mark.line + 1}:{mark.column + 1})")
        raise


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Namespace containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(description="OpenWeatherMap Prometheus Exporter")
    parser.add_argument("-f", "--file", dest="config_file", type=str, help="Path to config file")
    parser.add_argument("-v", "--verbose", dest="verbosity", action="count", default=0,
                      help="Increase verbosity (can be used multiple times)")
    return parser.parse_args()


def set_logging_level(_verbosity: int, _level: str, _logger: logging.Logger | None = None) -> logging.Logger:
    """Configure logging level and format.

    Args:
        _verbosity: Verbosity level from command line arguments
        _level: Logging level from configuration
        _logger: Optional existing logger instance

    Returns:
        Configured logger instance
    """
    _switcher = {
        1: "WARNING",
        2: "INFO",
        3: "DEBUG",
    }
    if _verbosity > 0:
        _level = _switcher.get(_verbosity, _level)

    _fmt = logging.Formatter(
        "%(asctime)s - %(module)s:%(lineno)d - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if _logger is None:
        _logger = logging.getLogger(__name__)

    # Remove existing handlers to avoid duplicates
    for handler in _logger.handlers[:]:
        _logger.removeHandler(handler)

    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)

    _logger.addHandler(_ch)
    _logger.setLevel(_level)
    _logger.info(f"Setting loglevel to {_level}")

    return _logger


def shutdown(_signal) -> None:
    """Signal handler to gracefully shut down the application."""
    global running
    running = False


if __name__ == "__main__":
    try:
        running = True
        args = parse_args()
        config = parse_config(args.config_file)

        if not config:
            raise ValueError("Invalid configuration")

        if getenv("TERM", None):
            signal.signal(signal.SIGTERM, shutdown)
            signal.signal(signal.SIGINT, shutdown)

        # Configuration with defaults and environment overrides
        interval: int = int(getenv("INTERVAL", config.get("interval", 600)))
        loglevel: str = getenv("LOGLEVEL", config.get("loglevel", "INFO"))
        listen_port: int = int(getenv("LISTEN_PORT", config.get("listen_port", 9126)))
        api_key: str | None = getenv("API_KEY", config.get("api_key"))
        units: str = getenv("UNITS", config.get("units", "C"))
        locations: list = config.get("locations", [])

        if not api_key:
            raise ValueError("API key is required")

        # Initialize logging
        log = set_logging_level(args.verbosity, loglevel)

        # Initialize metrics
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
        log.info(f"Exporter started on port {listen_port}")

        weather_api = OpenWeather(api_key)

        if not locations:
            raise ValueError("No locations specified in configuration")

        while running:
            try:
                for location in locations:
                    city = location.get("name")
                    if not city:
                        log.warning(f"Skipping location without name: {location}")
                        continue

                    try:
                        # Fetch weather data
                        if location.get("lat") is not None and location.get("lon") is not None:
                            data = weather_api.get_weather(lat=location["lat"], lon=location["lon"])
                        else:
                            data = weather_api.get_weather(city=city)

                        # Extract and validate main weather data
                        main_data = data.get("main", {})
                        sys_data = data.get("sys", {})
                        wind_data = data.get("wind", {})
                        clouds_data = data.get("clouds", {})
                        weather_data = data.get("weather", [{}])[0]

                        # Process temperature data
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

                        # Update metrics
                        country = sys_data.get("country", "unknown")

                        TEMPERATURE.labels(city, country).set(current_temperature)
                        TEMPERATURE_MIN.labels(city, country).set(min_temperature)
                        TEMPERATURE_MAX.labels(city, country).set(max_temperature)
                        TEMPERATURE_FEEL.labels(city, country).set(felt_temperature)
                        HUMIDITY.labels(city, country).set(main_data.get("humidity", 0))
                        PRESSURE.labels(city, country).set(main_data.get("pressure", 0))
                        WIND_DIRECTION.labels(city, country).set(wind_data.get("deg", 0))
                        WIND_SPEED.labels(city, country).set(wind_data.get("speed", 0))
                        CLOUDINESS.labels(city, country).set(clouds_data.get("all", 0))
                        SUNRISE_TIME.labels(city, country).set(sys_data.get("sunrise", 0))
                        SUNSET_TIME.labels(city, country).set(sys_data.get("sunset", 0))
                        WEATHER_CONDITION.labels(city, country, weather_data.get("description", "unknown")).set(1)

                        log.debug(f"Updated metrics for {city}, {country}")
                    except Exception as loc_error:
                        log.error(f"Error processing location {city}: {loc_error}")
                        continue

            except Exception as error:
                log.error(f"Error in main loop: {error}")
            finally:
                sleep(interval)

    except KeyboardInterrupt:
        print("Received interrupt signal, shutting down...")
    except Exception as error:
        print(f"Fatal error: {error}")
        raise
    finally:
        running = False

