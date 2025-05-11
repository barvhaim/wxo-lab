import json
from datetime import UTC, datetime
from typing import Literal, Optional
from urllib.parse import urlencode

import httpx
import requests
from pydantic import BaseModel, Field

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


class OpenMeteoToolInput(BaseModel):
    location_name: str = Field(
        description="The name of the location to retrieve weather information."
    )
    country: Optional[str] = Field(description="Country name.", default=None)
    start_date: Optional[str] = Field(
        description="Start date in the format YYYY-MM-DD (UTC)", default=None
    )
    end_date: Optional[str] = Field(
        description="End date in the format YYYY-MM-DD (UTC)", default=None
    )
    temperature_unit: Literal["celsius", "fahrenheit"] = Field(
        description="The unit to express temperature", default="celsius"
    )


def _geocode(location_name: str, country: Optional[str]) -> dict[str, str]:
    params = {"format": "json", "count": 1, "name": location_name}
    if country:
        params["country"] = country
    encoded_params = urlencode(params)
    response = requests.get(
        f"https://geocoding-api.open-meteo.com/v1/search?{encoded_params}",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError(f"Location '{location_name}' not found.")
    return results[0]


def _get_forecast_params(input: OpenMeteoToolInput, geocode: dict[str, str]) -> dict:
    current_date = datetime.now(tz=UTC).date()
    return {
        "latitude": geocode["latitude"],
        "longitude": geocode["longitude"],
        "current": "temperature_2m,rain,relative_humidity_2m,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,rain_sum",
        "timezone": "UTC",
        "start_date": input.start_date or str(current_date),
        "end_date": input.end_date or str(current_date),
        "temperature_unit": input.temperature_unit,
    }


@tool(
    name="getWeatherForecast",
    description="Retrieve weather forecast from OpenMeteo",
    permission=ToolPermission.ADMIN,
)
async def open_meteo_tool(input: OpenMeteoToolInput) -> str:
    """
    Retrieve weather forecast data from Open-Meteo.

    :param input: Input data including location, date range, and temperature unit.
    :returns: JSON string with weather forecast.
    """
    geocode = _geocode(input.location_name, input.country)
    params = _get_forecast_params(input, geocode)
    encoded = urlencode(params)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.open-meteo.com/v1/forecast?{encoded}",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
