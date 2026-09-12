import json
import os
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

import pg8000.dbapi as pg8000
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_NAME = os.environ["DB_NAME"]
API_TOKEN = os.environ["FOOTBALL_DATA_API_TOKEN"]

FEED_ID = "football_data_org"
API_BASE = "https://api.football-data.org/v4"

FREE_COMPETITIONS = [
    "PL", "PD", "BL1", "SA", "FL1", "CL", "ELC", "DED", "PPL", "EC", "WC", "BSA",
]


def api_get(path, params=None):
    url = f"{API_BASE}{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": API_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"football-data.org returned HTTP {e.code}: {body}") from e


def get_connection():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(
        host=DB_HOST, port=int(DB_PORT), database=DB_NAME,
        user=DB_USER, password=DB_PASS, ssl_context=ssl_context,
    )


def register_feed(conn):
    cur = conn.cursor()
    cur.execute(
        """
        insert into ops.source_feed_registry
            (feed_id, display_name, provider, source_type, access_method,
             license_notes, acquired_at, refresh_frequency, validation_status)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (feed_id) do update set
            acquired_at = excluded.acquired_at
        """,
        (
            FEED_ID,
            "football-data.org free tier fixtures/results",
            "football-data.org",
            "current_delayed",
            "free API token, email signup",
            "Free tier: 12 competitions, scores/schedules delayed (not live). "
            "10 requests/minute rate limit.",
            datetime.now(timezone.utc),
            "on-demand poll (run this script again to refresh)",
            "not_yet_validated",
        ),
    )
    cur.close()
    conn.commit()


def start_run(conn):
    cur = conn.cursor()
    cur.execute(
        "insert into ops.refresh_run (feed_id, status) values (%s, %s) returning run_id",
        (FEED_ID, "running"),
    )
    run_id = cur.fetchone()[0]
    cur.close()
    conn.commit()
    return run_id


def finish_run(conn, run_id, rows_ingested, status, error_message=None):
    cur = conn.cursor()
    cur.execute(
        """
        update ops.refresh_run
        set finished_at = now(), rows_ingested = %s, status = %s, error_message = %s
        where run_id = %s
        """,
        (rows_ingested, status, error_message, run_id),
    )
    cur.close()
    conn.commit()


def fetch_and_load(conn):
    date_from = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    date_to = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")

    data = api_get("/matches", {
        "competitions": ",".join(FREE_COMPETITIONS),
        "dateFrom": date_from,
        "dateTo": date_to,
    })

    matches = data.get("matches", [])
    print(f"Fetched {len(matches)} real matches from football-data.org "
          f"({date_from} to {date_to})")

    cur = conn.cursor()
    for m in matches:
        score = m.get("score", {}).get("fullTime", {}) or {}
        cur.execute(
            """
            insert into raw.football_data_fixtures
                (api_match_id, competition_code, season, utc_date_raw, status,
                 home_team, away_team, home_score, away_score, raw_payload)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                m["id"],
                m.get("competition", {}).get("code"),
                str(m.get("season", {}).get("startDate", ""))[:4],
                m.get("utcDate"),
                m.get("status"),
                m.get("homeTeam", {}).get("name"),
                m.get("awayTeam", {}).get("name"),
                score.get("home"),
                score.get("away"),
                json.dumps(m),
            ),
        )
    cur.close()
    conn.commit()
    return len(matches)


def main():
    conn = get_connection()
    try:
        register_feed(conn)
        run_id = start_run(conn)
        try:
            n = fetch_and_load(conn)
            finish_run(conn, run_id, n, "succeeded")
            print(f"Loaded {n} real fixtures into raw.football_data_fixtures (run_id={run_id}).")
        except Exception as e:
            conn.rollback()
            finish_run(conn, run_id, 0, "failed", str(e))
            raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
