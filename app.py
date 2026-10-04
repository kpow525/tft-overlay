import os

import requests
import time
from flask import Flask, jsonify

CACHE_DURATION = 300  # 5 minutes

stats_cache = {
    "timestamp": 0,
    "data": None,
}

app = Flask(__name__)

RIOT_API_KEY = os.environ["RIOT_API_KEY"]
RIOT_GAME_NAME = os.environ["RIOT_GAME_NAME"]
RIOT_TAG_LINE = os.environ["RIOT_TAG_LINE"]

REGION = "americas"

DOUBLE_UP_QUEUE_ID = 1100

HEADERS = {
    "X-Riot-Token": RIOT_API_KEY
}


def riot_get(url, params=None):
    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Riot API returned {response.status_code}: {response.text}"
        )

    return response.json()


def get_account():
    url = (
        f"https://{REGION}.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/"
        f"{RIOT_GAME_NAME}/{RIOT_TAG_LINE}"
    )

    return riot_get(url)


def get_match_ids(puuid, count=5):
    url = (
        f"https://{REGION}.api.riotgames.com"
        f"/tft/match/v1/matches/by-puuid/"
        f"{puuid}/ids"
    )

    return riot_get(url, params={"count": count})


def get_match(match_id):
    url = (
        f"https://{REGION}.api.riotgames.com"
        f"/tft/match/v1/matches/{match_id}"
    )

    return riot_get(url)


def get_double_up_stats(puuid, match_ids):
    placements = []

    double_up_matches = 0

    for match_id in match_ids:
        match = get_match(match_id)

        info = match["info"]

        if info.get("queue_id") != DOUBLE_UP_QUEUE_ID:
            continue

        double_up_matches += 1

        for participant in info["participants"]:
            if participant["puuid"] == puuid:
                placements.append(participant["placement"])
                break

    if not placements:
        return {
            "games": 0,
            "wins": 0,
            "win_rate": 0,
            "top2": 0,
            "top2_rate": 0,
            "average_placement": None,
        }

    games = len(placements)

    wins = sum(
        placement == 1
        for placement in placements
    )

    top2 = sum(
        placement <= 2
        for placement in placements
    )

    return {
        "games": games,
        "wins": wins,
        "win_rate": round(wins / games * 100, 2),
        "top2": top2,
        "top2_rate": round(top2 / games * 100, 2),
        "average_placement": round(
            sum(placements) / games,
            2,
        ),
    }


@app.route("/")
def home():
    return "TFT Double Up Overlay is running."


@app.route("/api/stats")
def stats():
    now = time.time()

    # Return cached data if it is still fresh
    if (
        stats_cache["data"] is not None
        and now - stats_cache["timestamp"] < CACHE_DURATION
    ):
        return jsonify(stats_cache["data"])

    account = get_account()

    puuid = account["puuid"]

    match_ids = get_match_ids(
        puuid,
        count=100,
    )

    double_up_stats = get_double_up_stats(
        puuid,
        match_ids,
    )

    data = {
        "riot_id": (
            f"{account['gameName']}#{account['tagLine']}"
        ),
        "queue": "Double Up",
        "queue_id": DOUBLE_UP_QUEUE_ID,
        **double_up_stats,
    }

    # Save result in cache
    stats_cache["timestamp"] = now
    stats_cache["data"] = data

    return jsonify(data)


@app.route("/api/refresh")
def refresh():
    stats_cache["timestamp"] = 0
    stats_cache["data"] = None

    return jsonify({
        "message": "Cache cleared. Next stats request will refresh from Riot."
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
    )