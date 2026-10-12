
import csv
import os
from pathlib import Path
from datetime import datetime, timezone

import requests

WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"].strip()
MESSAGE_FILE = Path("message_id.txt")
CSV_FILE = Path("us_chart.csv")

HEADERS = {
    "User-Agent": "RobloxTabAmericaLeaderboard/1.0",
}

GAMES_URL = "https://games.roblox.com/v1/games"


def get_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=25,
    )
    response.raise_for_status()
    return response.json()


def read_us_chart():
    """Read universe IDs in the order provided by the US chart CSV."""
    if not CSV_FILE.exists():
        raise RuntimeError(
            "Missing us_chart.csv. Export the US Top Playing Now "
            "chart from Rival Ducks and add the CSV to this repository."
        )

    ids = []
    seen = set()

    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise RuntimeError("The US chart CSV has no header row.")

        # Match common universe-ID column names.
        id_columns = {
            "universeid",
            "universe_id",
            "universe id",
            "gameuniverseid",
        }
        id_column = next(
            (
                column
                for column in reader.fieldnames
                if column.strip().lower() in id_columns
            ),
            None,
        )

        if id_column is None:
            raise RuntimeError(
                "Couldn't find a universe ID column in us_chart.csv. "
                f"CSV columns: {reader.fieldnames}"
            )

        for row in reader:
            try:
                universe_id = int(row[id_column].strip())
            except (TypeError, ValueError, AttributeError):
                continue

            if universe_id not in seen:
                seen.add(universe_id)
                ids.append(universe_id)

    if not ids:
        raise RuntimeError("No universe IDs were found in the US chart CSV.")

    print(f"US chart universe IDs found: {len(ids)}")
    return ids


def get_top_games():
    # Keep the order of the US chart. Use Roblox's API only for
    # worldwide metadata and concurrent player counts.
    ids = read_us_chart()
    games_by_id = {}

    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        data = get_json(
            GAMES_URL,
            {"universeIds": ",".join(map(str, batch))},
        )

        for game in data.get("data", []):
            games_by_id[game["id"]] = game

    games = []
    for universe_id in ids:
        game = games_by_id.get(universe_id)
        if game and isinstance(game.get("playing"), (int, float)):
            games.append(game)

    # Ranking follows the US chart order, not worldwide player count.
    games = games[:10]

    if not games:
        raise RuntimeError(
            "No games with worldwide player counts could be retrieved."
        )

    for rank, game in enumerate(games, 1):
        print(f'{rank}. {game.get("name", "Unknown")}: '
              f'{int(game["playing"]):,} global players')

    return games


def make_embed(games):
    lines = []

    for rank, game in enumerate(games, 1):
        name = game.get("name", "Unknown game")
        name = name.replace("[", "").replace("]", "")
        place_id = game.get("rootPlaceId")

        link = (
            f"https://www.roblox.com/games/{place_id}"
            if place_id
            else "https://www.roblox.com/charts/top-playing-now"
        )

        players = int(game["playing"])
        lines.append(
            f"**{rank}. [{name}]({link})** — "
            f"🌎 {players:,} global players"
        )

    return {
        "title": "🇺🇸 US Top 10 Roblox Games",
        "description": "\n".join(lines),
        "color": 0x00A2FF,
        "footer": {
            "text": "Roblox Tab • US chart ranking • Global player counts"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def publish(embed):
    message_id = (
        MESSAGE_FILE.read_text().strip()
        if MESSAGE_FILE.exists()
        else ""
    )

    if message_id:
        url = f"{WEBHOOK}/messages/{message_id}"
        response = requests.patch(
            url,
            json={"embeds": [embed]},
            timeout=25,
        )

        if response.status_code != 404:
            response.raise_for_status()
            print("Updated existing America leaderboard.")
            return

        print("Saved message was not found; creating a replacement.")

    response = requests.post(
        WEBHOOK,
        params={"wait": "true"},
        json={"embeds": [embed]},
        timeout=25,
    )
    response.raise_for_status()

    message_id = response.json()["id"]
    MESSAGE_FILE.write_text(message_id + "\n")
    print("Created America leaderboard:", message_id)


if __name__ == "__main__":
    games = get_top_games()
    publish(make_embed(games))
