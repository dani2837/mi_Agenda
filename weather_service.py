import json
import os
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv


load_dotenv(override=True)

_CACHE = {"expires_at": 0, "data": None}


WEATHER_CODES = {
    0: "Despejado",
    1: "Mayormente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna ligera",
    53: "Llovizna",
    55: "Llovizna intensa",
    61: "Lluvia ligera",
    63: "Lluvia",
    65: "Lluvia intensa",
    71: "Nieve ligera",
    73: "Nieve",
    75: "Nieve intensa",
    80: "Chubascos ligeros",
    81: "Chubascos",
    82: "Chubascos intensos",
    95: "Tormenta",
}


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def _weather_city() -> str:
    return os.getenv("WEATHER_CITY", "Madrid").strip() or "Madrid"


def _geocode_city(city: str) -> dict:
    params = urlencode({"name": city, "count": 1, "language": "es", "format": "json"})
    data = _get_json(f"https://geocoding-api.open-meteo.com/v1/search?{params}")
    results = data.get("results") or []
    if not results:
        raise ValueError(f"No encuentro la ciudad '{city}'.")
    return results[0]


def get_weather() -> dict:
    """Return current weather data for the city configured in .env."""
    now = time.time()
    if _CACHE["data"] and _CACHE["expires_at"] > now:
        return _CACHE["data"]

    city = _weather_city()

    try:
        place = _geocode_city(city)
        params = urlencode(
            {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": ",".join(
                    [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "weather_code",
                        "wind_speed_10m",
                    ]
                ),
                "daily": ",".join(
                    [
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_probability_max",
                    ]
                ),
                "timezone": "auto",
                "forecast_days": 3,
            }
        )
        data = _get_json(f"https://api.open-meteo.com/v1/forecast?{params}")
        current = data.get("current", {})
        daily = data.get("daily", {})
        weather_code = current.get("weather_code")
        max_temperatures = daily.get("temperature_2m_max") or []
        min_temperatures = daily.get("temperature_2m_min") or []

        weather = {
            "ok": True,
            "city": place.get("name", city),
            "country": place.get("country", ""),
            "description": WEATHER_CODES.get(weather_code, "Tiempo no disponible"),
            "temperature": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind": current.get("wind_speed_10m"),
            "max_temperature": max_temperatures[0] if len(max_temperatures) > 0 else None,
            "min_temperature": min_temperatures[0] if len(min_temperatures) > 0 else None,
            "tomorrow_max_temperature": max_temperatures[1] if len(max_temperatures) > 1 else None,
            "tomorrow_min_temperature": min_temperatures[1] if len(min_temperatures) > 1 else None,
            "after_tomorrow_max_temperature": max_temperatures[2] if len(max_temperatures) > 2 else None,
            "after_tomorrow_min_temperature": min_temperatures[2] if len(min_temperatures) > 2 else None,
            "rain_probability": (daily.get("precipitation_probability_max") or [None])[0],
        }
    except Exception as error:
        weather = {
            "ok": False,
            "city": city,
            "country": "",
            "error": str(error),
        }

    _CACHE["data"] = weather
    _CACHE["expires_at"] = now + 1800
    return weather


def format_weather_for_bot(weather: dict) -> str:
    if not weather["ok"]:
        return f"No he podido consultar el tiempo de {weather['city']}: {weather['error']}"

    return (
        f"Tiempo hoy en {weather['city']}:\n"
        f"{weather['description']}\n"
        f"Temperatura: {weather['temperature']} grados\n"
        f"Sensacion: {weather['apparent_temperature']} grados\n"
        f"Maxima: {weather['max_temperature']} grados\n"
        f"Minima: {weather['min_temperature']} grados\n"
        f"Lluvia: {weather['rain_probability']}%\n"
        f"Humedad: {weather['humidity']}%\n"
        f"Viento: {weather['wind']} km/h"
    )
