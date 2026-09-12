import csv
import json
import glob
import os
from collections import Counter

from SoccerNet.Downloader import SoccerNetDownloader

LOCAL_DIR = "soccernet_data"
SPLITS = ["valid"]

def download():
    downloader = SoccerNetDownloader(LocalDirectory=LOCAL_DIR)
    downloader.downloadGames(files=["Labels-v2.json"], split=SPLITS)
    print(f"Downloaded real SoccerNet Labels-v2.json files into ./{LOCAL_DIR}/")

def flatten_to_csv():
    label_files = glob.glob(os.path.join(LOCAL_DIR, "**", "Labels-v2.json"), recursive=True)
    print(f"Found {len(label_files)} real Labels-v2.json files")

    fieldnames = ["game_id", "competition", "season", "half", "game_time_raw",
                  "action_class", "team", "visibility"]
    out_path = "soccernet_action_events_raw.csv"
    action_counts = Counter()
    row_count = 0

    with open(out_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()

        for path in label_files:
            game_id = os.path.dirname(path).replace(LOCAL_DIR + os.sep, "")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            competition = data.get("competition")
            season = data.get("season")

            for ann in data.get("annotations", []):
                half_str, time_str = ann["gameTime"].split(" - ")
                action_class = ann.get("label")
                writer.writerow({
                    "game_id": game_id,
                    "competition": competition,
                    "season": season,
                    "half": int(half_str),
                    "game_time_raw": time_str,
                    "action_class": action_class,
                    "team": ann.get("team"),
                    "visibility": ann.get("visibility"),
                })
                action_counts[action_class] += 1
                row_count += 1

    print(f"Wrote {row_count} real action-spotting events to {out_path}")
    for action_class, count in action_counts.most_common():
        print(f"  {action_class}: {count}")

if __name__ == "__main__":
    download()
    flatten_to_csv()
