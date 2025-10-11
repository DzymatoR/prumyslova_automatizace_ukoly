# -*- coding: utf-8 -*-
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import timedelta
import plotly.express as px
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go

# ---------- HTTP session s retry ----------
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
session.mount("https://", HTTPAdapter(max_retries=retries))

API_URL = "https://api.open-meteo.com/v1/forecast"

# ---------- Krajská města ČR (město, kraj, lat, lon) ----------
cities = [
    ("Praha", "Hlavní město Praha", 50.0755, 14.4378),
    ("Brno", "Jihomoravský kraj", 49.1951, 16.6068),
    ("Ostrava", "Moravskoslezský kraj", 49.8209, 18.2625),
    ("Plzeň", "Plzeňský kraj", 49.7384, 13.3736),
    ("Liberec", "Liberecký kraj", 50.7671, 15.0562),
    ("Olomouc", "Olomoucký kraj", 49.5938, 17.2509),
    ("Ústí nad Labem", "Ústecký kraj", 50.6600, 14.0400),
    ("Hradec Králové", "Královéhradecký kraj", 50.2092, 15.8328),
    ("Pardubice", "Pardubický kraj", 50.0343, 15.7812),
    ("Jihlava", "Kraj Vysočina", 49.3961, 15.5912),
    ("Zlín", "Zlínský kraj", 49.2244, 17.6627),
    ("České Budějovice", "Jihočeský kraj", 48.9747, 14.4749),
    ("Karlovy Vary", "Karlovarský kraj", 50.2310, 12.8710),
]

def get_current_weather(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m",
        "timezone": "Europe/Prague",
        "timeformat": "iso8601",
    }
    r = session.get(API_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    cur = data.get("current", {})
    return {
        "iso_time": cur.get("time"),
        "temperature": cur.get("temperature_2m"),
        "apparent_temperature": cur.get("apparent_temperature"),
        "humidity": cur.get("relative_humidity_2m"),
        "wind_speed": cur.get("wind_speed_10m"),
        "timezone": data.get("timezone"),
    }

def get_hourly_last_24h(lat, lon):
    """Hodinová teplota za posledních ~24 h (vezmeme 48 h a vezmeme posledních 24, spolehlivější přes půlnoc)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m",
        "past_days": 2,
        "timezone": "Europe/Prague",
        "timeformat": "iso8601",
    }
    r = session.get(API_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    if not times or not temps:
        return pd.DataFrame(columns=["time", "temperature_2m"])

    df = pd.DataFrame({"time": pd.to_datetime(times), "temperature_2m": temps})
    t_max = df["time"].max()
    t_min = t_max - timedelta(hours=24)
    return df[(df["time"] > t_min) & (df["time"] <= t_max)].reset_index(drop=True)

# ---------- Data pro mapu ----------
rows = []
for city, region, lat, lon in cities:
    try:
        w = get_current_weather(lat, lon)
        rows.append({
            "Město": city, "Kraj": region,
            "Latitude": lat, "Longitude": lon,
            "Lokální čas": w["iso_time"],
            "Teplota [°C]": w["temperature"],
            "Pocitově [°C]": w["apparent_temperature"],
            "Vlhkost [%]": w["humidity"],
            "Vítr [m/s]": w["wind_speed"],
            "Timezone": w["timezone"],
        })
    except Exception as e:
        print(f"⚠️  {city}: {e}")

df_map = pd.DataFrame(rows).dropna(subset=["Teplota [°C]"]).reset_index(drop=True)

def build_map_figure(df):
    fig = px.scatter_mapbox(
        df,
        lat="Latitude",
        lon="Longitude",
        color="Teplota [°C]",
        size="Teplota [°C]",
        size_max=24,
        color_continuous_scale="Turbo",
        hover_name="Město",
        hover_data={
            "Kraj": True,
            "Teplota [°C]": True,
            "Pocitově [°C]": True,
            "Vlhkost [%]": True,
            "Vítr [m/s]": True,
            "Lokální čas": True,
        },
        title="Aktuální teploty v krajských městech ČR (Open-Meteo) – klikni na město",
        custom_data=["Město", "Kraj", "Latitude", "Longitude"]
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(center=dict(lat=49.8, lon=15.5), zoom=6.2),
        margin=dict(l=0, r=0, t=60, b=0),
        coloraxis_colorbar=dict(title="Teplota [°C]"),
    )
    return fig

# ---------- Dash aplikace ----------
app = Dash(__name__)
app.title = "ČR Weather Map"

app.layout = html.Div([
    dcc.Graph(id="map", figure=build_map_figure(df_map), style={"height": "65vh"}),
    html.Div(id="city-title", style={"fontSize": "20px", "fontWeight": "600", "margin":"10px 0"}),
    dcc.Graph(id="timeseries", style={"height": "28vh"}),
])

@app.callback(
    Output("timeseries", "figure"),
    Output("city-title", "children"),
    Input("map", "clickData"),
    prevent_initial_call=False
)
def update_timeseries(clickData):
    # výchozí: první město v tabulce (např. Praha)
    if not clickData:
        row = df_map.iloc[0]
        city, region, lat, lon = row["Město"], row["Kraj"], row["Latitude"], row["Longitude"]
    else:
        p = clickData["points"][0]["customdata"]
        city, region, lat, lon = p[0], p[1], float(p[2]), float(p[3])

    df24 = get_hourly_last_24h(lat, lon)

    if df24.empty:
        fig = go.Figure()
        fig.update_layout(title=f"Žádná hodinová data pro {city}", margin=dict(l=0, r=0, t=40, b=0))
        return fig, f"{city} – posledních 24 h"

    fig = px.line(df24, x="time", y="temperature_2m", title=f"Teplota za posledních 24 h – {city} ({region})", markers=True)
    fig.update_layout(xaxis_title="Čas", yaxis_title="Teplota [°C]", margin=dict(l=0, r=10, t=40, b=0))
    return fig, f"{city} ({region}) – klikni na jiné město pro změnu"

if __name__ == "__main__":
    # Dash 2.16+: používej app.run()
    app.run(debug=True)
