
import os
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

import requests

WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"].strip()
MESSAGE_FILE = Path("message_id.txt")
SESSION = str(uuid.uuid4())
HEADERS = {"User-Agent": "RobloxTabLeaderboard/1.0"}


def get_json(url, params=None):
    response = requests.get(
        url, params=params, headers=HEADERS, timeout=25
    )
    response.raise_for_status()
    return response.json()


def find_universe_ids(data):
    ids = set()

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() in ("universeid", "universe_id"):
                    try:
                        ids.add(int(value))
                    except (TypeError, ValueError):
                        pass
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str) and obj.startswith(("{", "[")):
            try:
                walk(json.loads(obj))
            except json.JSONDecodeError:
                pass

    walk(data)
    return ids


def get_top_games():
    discovery = get_json(
        "https://apis.roblox.com/explore-api/v1/get-sort-content",
        {
            "sessionId": SESSION,
            "sortId": "top-playing-now",
            "device": "computer",
            "country": "all",
            "maxRows": 50,
        },
    )

    ids = list(find_universe_ids(discovery))[:50]
    if not ids:
        raise RuntimeError(
            "No game IDs found. Roblox may have changed its API."
        )

    games = []
    for start in range(0, len(ids), 10):
        batch = ids[start:start + 10]
        data = get_json(
            "https://games.roblox.com/v1/games",
            {"universeIds": ",".join(map(str, batch))},
        )
        games.extend(data.get("data", []))

    games = [
        game for game in games
        if isinstance(game.get("playing"), (int, float))
    ]
    games.sort(key=lambda game: game["playing"], reverse=True)
    return games[:10]


def make_embed(games):
    lines = []

    for rank, game in enumerate(games, 1):
        name = game.get("name", "Unknown game")
        name = name.replace("[", "").replace("]", "")
        place_id = game.get("rootPlaceId")
        link = (
            f"https://www.roblox.com/games/{place_id}"
            if place_id else
            "https://www.roblox.com/charts/top-playing-now"
        )
        players = int(game["playing"])
        lines.append(
            f"**{rank}. [{name}]({link})** — "
            f"👥 {players:,} playing"
        )

    return {
        "title": "🏆 Top 10 Roblox Games Right Now",
        "description": "\n".join(lines),
        "color": 0x00A2FF,
        "footer": {"text": "Roblox Tab • Refreshes every 10 minutes"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def publish(embed):
    message_id = (
        MESSAGE_FILE.read_text().strip()
        if MESSAGE_FILE.exists() else ""
    )

    if message_id:
        url = f"{WEBHOOK}/messages/{message_id}"
        response = requests.patch(
            url, json={"embeds": [embed]}, timeout=25
        )
        if response.status_code != 404:
            response.raise_for_status()
            print("Updated existing leaderboard.")
            return
        print("Old message missing; creating a replacement.")

    response = requests.post(
        WEBHOOK,
        params={"wait": "true"},
        json={"embeds": [embed]},
        timeout=25,
    )
    response.raise_for_status()
    message_id = response.json()["id"]
    MESSAGE_FILE.write_text(message_id + "\n")
    print("Created leaderboard:", message_id)


if __name__ == "__main__":
    games = get_top_games()
    if not games:
        raise RuntimeError("Roblox returned no games.")
    publish(make_embed(games))
