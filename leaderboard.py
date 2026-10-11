
import os
import requests
from datetime import datetime, timezone

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

def get_top_games():
    url = "https://games.roblox.com/v1/games/sorts"
    params = {
        "sortType": "1",
        "timeFilter": "0",
        "gameFilter": "1",
        "limit": "10",
    }
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json().get("games", [])

def make_embed(games):
    lines = []
    for i, game in enumerate(
        sorted(games, key=lambda g: g.get("playing", 0), reverse=True), 1
    ):
        name = game.get("name", "Unknown game")
        players = int(game.get("playing", 0))
        place_id = game.get("placeId")
        link = f"https://www.roblox.com/games/{place_id}" if place_id else "https://www.roblox.com/charts/top-playing-now"
        lines.append(f"**{i}. [{name}]({link})** — 👥 {players:,} playing")

    return {
        "title": "🏆 Top 10 Roblox Games Right Now",
        "description": "\n".join(lines) or "No games returned by Roblox.",
        "color": 0x00A2FF,
        "footer": {"text": "Roblox Tab • Updated every 10 minutes"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def main():
    games = get_top_games()
    embed = make_embed(games)

    # Save the Discord message ID between workflow runs.
    message_id = os.environ.get("DISCORD_MESSAGE_ID", "").strip()
    match_url = WEBHOOK_URL.rstrip("/")
    if message_id:
        url = f"{match_url}/messages/{message_id}"
        response = requests.patch(url, json={"embeds": [embed]}, timeout=20)
        response.raise_for_status()
    else:
        response = requests.post(
            match_url,
            params={"wait": "true"},
            json={"embeds": [embed]},
            timeout=20,
        )
        response.raise_for_status()
        print("First message created:", response.json().get("id"))

if __name__ == "__main__":
    main()
