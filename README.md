# openweathermap-exporter

Simple Openweathermap Exporter for Prometheus

## Installation

* Create an [Openweathermap API Account](https://openweathermap.org/api) and create an api key there.

```yaml
interval: 600 # OpenWeatherMap weather data is only updated every 10 minutes. So there is no need to poll more often than that.
loglevel: INFO
listen_port: 9126

api_key: ""
units: "C" # can be C (Celsius), F (Fahrenheit) or K (Kelvin)

locations:
  - name: "London"
    lat: 51.5085
    lon: -0.1257
  - name: "Berlin"
    lat: 52.5244
    lon: 13.4105
```

As a minimum locations have to be defined. The rest can be set as environment variables.

```
INTERVAL=600
LOGLEVEL=INFO
LISTEN_PORT=9126

API_KEY=""
UNITS="C"
```

Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: openweathermap-exporter
    scrape_interval: 10m
    static_configs:
      - targets: ['openweathermap-exporter:9126']
