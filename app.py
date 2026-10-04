import os

import requests
import time
from flask import Flask, jsonify, render_template, request

CACHE_DURATION = 300  # 5 minutes

stats_cache = {}

app = Flask(__name__)

RIOT_API_KEY = os.environ["RIOT_API_KEY"]
RIOT_GAME_NAME = os.environ["RIOT_GAME_NAME"]
RIOT_TAG_LINE = os.environ["RIOT_TAG_LINE"]

REGION = "americas"
REGION_ID = "na1"

DOUBLE_UP_QUEUE_ID = 1160
QUEUE_TYPE = "RANKED_TFT_DOUBLE_UP"

TOTAL_REQUESTS = 0

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
            f"Total requests were: {TOTAL_REQUESTS}. Riot API returned {response.status_code}: {response.text}"
        )

    return response.json()


def get_account():
    url = (
        f"https://{REGION}.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/"
        f"{game_name}/{tag_line}"
    )

    global TOTAL_REQUESTS
    TOTAL_REQUESTS += 1

    return riot_get(url)


def get_tft_rank_data(puuid):
    url = (
        f"https://{REGION_ID}.api.riotgames.com"
        f"/tft/league/v1/by-puuid/"
        f"{puuid}"
    )
    
    global TOTAL_REQUESTS
    TOTAL_REQUESTS += 1

    return riot_get(url)


def get_double_up_data(data):
    double_up = next(item for item in data if item["queueType"] == QUEUE_TYPE)
    games = double_up["wins"] + double_up["losses"]
    winrate = double_up["wins"]/games * 100

    return{
        "tier": double_up["tier"],
        "rank": double_up["rank"],
        "lp": double_up["leaguePoints"],
        "games": games,
        "wins": double_up["wins"],
        "losses": double_up["losses"],
        "winrate": round(winrate,2)
    }


def get_match_ids(puuid, count=20):
    url = (
        f"https://{REGION}.api.riotgames.com"
        f"/tft/match/v1/matches/by-puuid/"
        f"{puuid}/ids"
    )

    global TOTAL_REQUESTS
    TOTAL_REQUESTS += 1

    return riot_get(url, params={"count": count})


def get_match(match_id):
    url = (
        f"https://{REGION}.api.riotgames.com"
        f"/tft/match/v1/matches/{match_id}"
    )

    global TOTAL_REQUESTS
    TOTAL_REQUESTS += 1

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
        "games/20": games,
        "wins/20": wins,
        "win_rate/20": round(wins / games * 100, 2),
        "top2/20": top2,
        "top2_rate/20": round(top2 / games * 100, 2),
        "average_placement/20": round(
            sum(placements) / games,
            2,
        ),
    }


@app.route("/")
def home():
    return "TFT Double Up Overlay is running."


@app.route("/api/stats")
def stats():
    game_name = request.args.get("gameName")
    tag_line = request.args.get("tagLine")

    if not game_name or not tag_line:
        return jsonify({
            "error": "gameName and tagLine are required"
        }), 400

    cache_key = f"{game_name.lower()}#{tag_line.lower()}"

    now = time.time()

    if cache_key in stats_cache:
        cached = stats_cache[cache_key]

        if now - cached["timestamp"] < CACHE_DURATION:
            return jsonify(cached["data"])
    
    # Return cached data if it is still fresh
    if (
        stats_cache["data"] is not None
        and now - stats_cache["timestamp"] < CACHE_DURATION
    ):
        return jsonify(stats_cache["data"])

    account = get_account(game_name, tag_line)

    puuid = account["puuid"]

    tft_rank_data = get_tft_rank_data(puuid)

    double_up_data = get_double_up_data(tft_rank_data)

    match_ids = get_match_ids(
        puuid,
        count=20,
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
        # **double_up_stats,
        **double_up_data,
    }

    # Save result in cache
    stats_cache[cache_key] = {
        "timestamp": now,
        "data": data,
    }

    return jsonify(data)


@app.route("/api/refresh")
def refresh():
    stats_cache["timestamp"] = 0
    stats_cache["data"] = None

    return jsonify({
        "message": "Cache cleared. Next stats request will refresh from Riot."
    })

@app.route("/doubleup")
def doubleup():
    return render_template("doubleup.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
    )