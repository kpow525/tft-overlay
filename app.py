import os

import requests
from flask import Flask, jsonify

app = Flask(__name__)

RIOT_API_KEY = os.environ["RIOT_API_KEY"]
RIOT_GAME_NAME = os.environ["RIOT_GAME_NAME"]
RIOT_TAG_LINE = os.environ["RIOT_TAG_LINE"]

ACCOUNT_REGION = "americas"
TFT_REGION = "americas"

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


@app.route("/")
def home():
    return "TFT Double Up Overlay is running."


@app.route("/api/debug")
def debug():
    # Resolve Riot ID -> PUUID
    account_url = (
        f"https://{ACCOUNT_REGION}.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/"
        f"{RIOT_GAME_NAME}/{RIOT_TAG_LINE}"
    )

    account = riot_get(account_url)
    puuid = account["puuid"]

    # Get recent TFT matches
    matches_url = (
        f"https://{TFT_REGION}.api.riotgames.com"
        f"/tft/match/v1/matches/by-puuid/"
        f"{puuid}/ids"
    )

    match_ids = riot_get(
        matches_url,
        params={"count": 20}
    )

    queue_ids = {}

    for match_id in match_ids:
        match_url = (
            f"https://{TFT_REGION}.api.riotgames.com"
            f"/tft/match/v1/matches/{match_id}"
        )

        match = riot_get(match_url)

        queue_id = match["info"].get("queue_id")

        queue_ids[str(queue_id)] = (
            queue_ids.get(str(queue_id), 0) + 1
        )

    return jsonify({
        "riot_id": f"{account['gameName']}#{account['tagLine']}",
        "puuid_found": bool(puuid),
        "matches_found": len(match_ids),
        "queue_ids": queue_ids,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)