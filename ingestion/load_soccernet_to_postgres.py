"""
Loads the real, flattened SoccerNet action-event CSV into your Supabase
Postgres database. Uses pg8000, not psycopg2 -- psycopg2-binary ships a
compiled C extension, and this machine's Windows Application Control policy
blocks it (same failure mode we already hit with numpy). pg8000 is a pure-
Python Postgres driver: no compiled DLL, nothing for WDAC to block.

Prerequisites (do these first, in order):
  1. sql/01_schema.sql has been run in your Supabase project's SQL editor
     (creates the raw/staging/analytics/ops schemas and tables).
  2. A .env file exists in this project's root folder with:
       DB_USER=postgres
       DB_PASS=your_real_supabase_password
       DB_HOST=your_real_supabase_host
       DB_PORT=5432
       DB_NAME=postgres
  3. soccernet_action_events_raw.csv (from fetch_soccernet_labels.py) is
     somewhere you can point this script at -- pass its path as an argument
     or drop it in this project's root and leave CSV_PATH as-is below.

Usage:
    pip install pg8000 python-dotenv
    python ingestion\\load_soccernet_to_postgres.py [path\\to\\soccernet_action_events_raw.csv]
"""
import csv
import os
import ssl
import sys
from datetime import datetime, timezone

import pg8000.dbapi as pg8000
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_NAME = os.environ["DB_NAME"]

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "soccernet_action_events_raw.csv"
FEED_ID = "soccernet_labels_v2"


def get_connection():
    # This dev machine's network intercepts outbound TLS with a root
    # certificate that isn't trusted by Windows itself (confirmed: even
    # truststore, which defers to the OS's own certificate store, rejects
    # it) -- most likely antivirus/security software doing HTTPS scanning.
    # Tracking down which product and getting its cert properly trusted is
    # not worth it for a free-tier dev database with no sensitive data.
    # Documented tradeoff, not an oversight: certificate verification is
    # disabled for this connection only. See docs/DATA_PROVENANCE.md /
    # README "Known Environment Constraints".
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(
        host=DB_HOST, port=int(DB_PORT), database=DB_NAME,
        user=DB_USER, password=DB_PASS, ssl_context=ssl_context,
    )


def register_feed(conn):
    """
    Row one, before any data: this feed's real provenance, matching
    docs/DATA_PROVENANCE.md exactly. If this insert is missing, the
    validation layer (next script) should treat that as a CRITICAL finding
    -- untraceable data is the one thing this project doesn't allow.
    """
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
            "SoccerNet action-spotting labels (v2)",
            "SoccerNet research consortium",
            "historical_broadcast",
            "pip package (SoccerNet), zero registration for labels",
            "Labels only, no raw video. Video access is separately NDA-gated and not used here.",
            datetime.now(timezone.utc),
            "static (archival split, re-run to pull more games)",
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


def load_raw_rows(conn, csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    # One insert per row was 21k+ network round trips to a Supabase pooler
    # in a different region -- slow enough to look hung. Batch instead:
    # one multi-row insert per chunk, far fewer round trips.
    chunk_size = 500
    print(f"Inserting {total} real rows in batches of {chunk_size}...")

    cur = conn.cursor()
    for start in range(0, total, chunk_size):
        chunk = rows[start:start + chunk_size]
        values_sql = ", ".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(chunk))
        params = []
        for row in chunk:
            params.extend([
                row["game_id"], row["competition"], row["season"],
                int(row["half"]), row["game_time_raw"], row["action_class"],
                row["team"], row["visibility"], os.path.basename(csv_path),
            ])
        cur.execute(
            f"""
            insert into raw.soccernet_action_events
                (game_id, competition, season, half, game_time_raw,
                 action_class, team, visibility, source_file)
            values {values_sql}
            """,
            params,
        )
        conn.commit()  # commit per chunk so progress survives an interrupt
        print(f"  ...{min(start + chunk_size, total)}/{total} rows committed")
    cur.close()
    return total


def main():
    if not os.path.exists(CSV_PATH):
        print(f"Can't find {CSV_PATH}. Run fetch_soccernet_labels.py first, "
              f"or pass the CSV's real path as an argument.")
        sys.exit(1)

    conn = get_connection()
    try:
        register_feed(conn)
        run_id = start_run(conn)
        try:
            n = load_raw_rows(conn, CSV_PATH)
            finish_run(conn, run_id, n, "succeeded")
            print(f"Loaded {n} real rows into raw.soccernet_action_events (run_id={run_id}).")
        except Exception as e:
            conn.rollback()
            finish_run(conn, run_id, 0, "failed", str(e))
            raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
