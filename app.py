import os

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return "TFT Double Up Overlay is running."


@app.route("/api/stats")
def stats():
    return jsonify({
        "rank": "Diamond II",
        "lp": 74,
        "games": 128,
        "wins": 35,
        "win_rate": 27.34,
        "top2": 79,
        "top2_rate": 61.72,
        "average_placement": 2.18,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)