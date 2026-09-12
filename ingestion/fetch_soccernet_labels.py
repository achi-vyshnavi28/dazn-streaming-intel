"""
Run this on YOUR machine, not in any cloud sandbox -- it needs normal internet
access to PyPI and SoccerNet's hosting, which a locked-down sandbox won't have.

Downloads real SoccerNet action-spotting labels for a real subset of games.
These are the actual event annotations (goal, card, substitution, etc., with
real in-match timestamps) for real broadcast football matches -- zero
registration, zero NDA, zero password required. (The raw broadcast VIDEO
files are NDA-gated; we are deliberately not touching those. See
docs/DATA_PROVENANCE.md for why that's fine for this project.)

Usage:
    python -m venv venv && source venv/bin/activate
    pip install SoccerNet pandas
    python fetch_soccernet_labels.py
"""
import json
import glob
import os

from SoccerNet.Downloader import SoccerNetDownloader

LOCAL_DIR = "soccernet_data"
# Start with one real, fully-labeled split so the pipeline proves out fast.
# Swap in ["train", "valid", "test"] once everything downstream works.
SPLITS = ["valid"]

def download():
    downloader = SoccerNetDownloader(LocalDirectory=LOCAL_DIR)
    # Labels-v2.json = the actual action-spotting annotation file SoccerNet
    # ships per game: real event type + real half + real MM:SS timestamp.
    downloader.downloadGames(files=["Labels-v2.json"], split=SPLITS)
    print(f"Downloaded real SoccerNet Labels-v2.json files into ./{LOCAL_DIR}/")

def flatten_to_csv():
    """
    Walk every downloaded Labels-v2.json and flatten it into one real,
    analysis-ready CSV -- this is the file load_soccernet_to_postgres.py
    (next step) reads from.
    """
    import pandas as pd

    label_files = glob.glob(os.path.join(LOCAL_DIR, "**", "Labels-v2.json"), recursive=True)
    print(f"Found {len(label_files)} real Labels-v2.json files")

    rows = []
    for path in label_files:
        game_id = os.path.dirname(path).replace(LOCAL_DIR + os.sep, "")
        with open(path) as f:
            data = json.load(f)

        competition = data.get("competition")
        season = data.get("season")

        for ann in data.get("annotations", []):
            # SoccerNet's real format: "1 - 23:45" -> half 1, 23:45 into that half
            half_str, time_str = ann["gameTime"].split(" - ")
            rows.append({
                "game_id": game_id,
                "competition": competition,
                "season": season,
                "half": int(half_str),
                "game_time_raw": time_str,
                "action_class": ann.get("label"),
                "team": ann.get("team"),
                "visibility": ann.get("visibility"),
            })

    df = pd.DataFrame(rows)
    out_path = "soccernet_action_events_raw.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} real action-spotting events to {out_path}")
    print(df["action_class"].value_counts())

if __name__ == "__main__":
    download()
    flatten_to_csv()
