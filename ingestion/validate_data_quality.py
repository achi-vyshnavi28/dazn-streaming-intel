"""
Real data-quality validation over the staging layer -- not a demo, actual
checks with actual thresholds, writing structured PASS/WARNING/CRITICAL
rows into ops.validation_check and opening real ops.incident rows when
something is genuinely wrong. This is the trust layer the rest of this
project (BI, LookML, the agent) is allowed to assume holds.

Uses pg8000, same as the ingestion scripts -- see those for why (WDAC
blocks psycopg2-binary's compiled DLL on this machine) -- and disables TLS
cert verification for the same documented reason (this network's TLS
interception isn't trusted even by Windows itself). See
docs/DATA_PROVENANCE.md / README "Known Environment Constraints".

Run this AFTER sql/02_staging_transform.sql, every time staging is
refreshed.

Usage:
    python ingestion\\validate_data_quality.py
"""
import os
import ssl
from datetime import datetime, timezone

import pg8000.dbapi as pg8000
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_NAME = os.environ["DB_NAME"]

# The 17 real SoccerNet action-spotting classes. Used to catch label-schema
# drift or a parsing bug -- not to filter or clean data.
KNOWN_ACTION_CLASSES = {
    "Ball out of play", "Throw-in", "Foul", "Indirect free-kick",
    "Clearance", "Shots on target", "Shots off target", "Corner",
    "Substitution", "Kick-off", "Direct free-kick", "Offside",
    "Yellow card", "Goal", "Penalty", "Red card", "Yellow->red card",
}


def get_connection():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return pg8000.connect(
        host=DB_HOST, port=int(DB_PORT), database=DB_NAME,
        user=DB_USER, password=DB_PASS, ssl_context=ssl_context,
    )


def fetch_one(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    row = cur.fetchone()
    cur.close()
    return row


def fetch_all(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    return rows


def record_check(conn, check_name, dataset, field, status, expected, actual,
                  impact, recommended_action=None):
    cur = conn.cursor()
    cur.execute(
        """
        insert into ops.validation_check
            (run_id, check_name, dataset, field, status, expected, actual,
             impact, recommended_action)
        values (null, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (check_name, dataset, field, status, str(expected), str(actual),
         impact, recommended_action),
    )
    cur.close()
    conn.commit()
    print(f"  [{status}] {check_name} -- expected {expected}, actual {actual}")


def open_incident(conn, source, dataset, category, issue, severity,
                   affected_records, affected_metric, likely_cause, recommended_owner):
    cur = conn.cursor()
    cur.execute(
        """
        insert into ops.incident
            (source, dataset, category, issue, severity, affected_records,
             affected_metric, likely_cause, recommended_owner)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (source, dataset, category, issue, severity, affected_records,
         affected_metric, likely_cause, recommended_owner),
    )
    cur.close()
    conn.commit()
    print(f"  INCIDENT OPENED [{severity}]: {issue}")


def check_row_count_sanity(conn):
    """raw -> staging row-count drop should be small. Some drop is expected
    (the staging transform defensively skips malformed game_time_raw values
    rather than crash) -- but a large drop means something's actually
    broken, not just a handful of dirty rows."""
    raw_events = fetch_one(conn, "select count(*) from raw.soccernet_action_events")[0]
    staging_events = fetch_one(conn, "select count(*) from staging.action_event")[0]
    drop_pct = round(100 * (raw_events - staging_events) / raw_events, 2) if raw_events else 0

    status = "PASS" if drop_pct <= 1.0 else ("WARNING" if drop_pct <= 5.0 else "CRITICAL")
    record_check(
        conn, "raw_to_staging_row_count_sanity", "staging.action_event", "game_time_raw",
        status, f"<=1% drop from raw ({raw_events} rows)",
        f"{drop_pct}% drop ({staging_events} rows)",
        "affects total action-event volume used in every downstream metric",
        "inspect rows dropped by the game_time_raw filter in 02_staging_transform.sql" if status != "PASS" else None,
    )
    if status == "CRITICAL":
        open_incident(
            conn, "staging_transform", "staging.action_event", "DATA_ISSUE",
            f"{drop_pct}% of raw SoccerNet events were dropped during staging (expected <=1%)",
            "HIGH", raw_events - staging_events, "action_event_count",
            "malformed game_time_raw values, or a regex/parsing regression",
            "Data Engineering",
        )


def check_match_field_completeness(conn):
    """Covers every dimension a downstream rollup groups or joins by.
    competition/season are included deliberately: a real bug (SoccerNet's
    actual Labels-v2.json has no top-level competition/season keys, so the
    ingestion script's data.get("competition") silently returned None for
    every row) collapsed analytics.competition_action_rates from 17 real
    rows down to 1 before this check existed to catch it. It's here now so
    the next silent-null bug doesn't require a human eyeballing a
    suspiciously low row count to notice."""
    total = fetch_one(conn, "select count(*) from staging.match")[0]
    nulls = fetch_one(conn, """
        select count(*) from staging.match
        where home_team is null or away_team is null or match_date is null
           or competition is null or season is null
    """)[0]
    null_pct = round(100 * nulls / total, 2) if total else 0

    status = "PASS" if nulls == 0 else ("WARNING" if null_pct <= 2.0 else "CRITICAL")
    record_check(
        conn, "staging_match_field_completeness", "staging.match",
        "home_team/away_team/match_date/competition/season",
        status, "0 nulls", f"{nulls} nulls ({null_pct}%)",
        "any null here breaks match-level joins and competition/season grouping for every downstream report",
        "check the game_id parsing in 02_staging_transform.sql against the null rows' raw.game_id" if status != "PASS" else None,
    )
    if status != "PASS":
        open_incident(
            conn, "staging_transform", "staging.match", "DATA_ISSUE",
            f"{nulls} matches have a null home_team, away_team, match_date, competition, or season after staging",
            "HIGH" if status == "CRITICAL" else "MEDIUM", nulls, "match_count",
            "game_id values that don't match the expected SoccerNet path pattern, or a broken upstream field mapping",
            "Data Engineering",
        )


def check_duplicate_matches(conn):
    total = fetch_one(conn, "select count(*) from staging.match")[0]
    distinct = fetch_one(conn, "select count(distinct match_id) from staging.match")[0]
    dupes = total - distinct
    status = "PASS" if dupes == 0 else "CRITICAL"
    record_check(
        conn, "staging_match_no_duplicate_ids", "staging.match", "match_id",
        status, "0 duplicate match_id", f"{dupes} duplicates",
        "duplicate matches would double-count fixtures in every match-level metric",
        "should be impossible given match_id's primary key -- if this fires, investigate immediately" if status != "PASS" else None,
    )


def check_action_class_drift(conn):
    rows = fetch_all(conn, "select distinct action_class from staging.action_event")
    seen = {r[0] for r in rows}
    unknown = seen - KNOWN_ACTION_CLASSES
    status = "PASS" if not unknown else "WARNING"
    record_check(
        conn, "action_class_known_value_set", "staging.action_event", "action_class",
        status, f"subset of {len(KNOWN_ACTION_CLASSES)} known SoccerNet classes",
        f"{len(unknown)} unknown classes: {sorted(unknown)}" if unknown else "0 unknown classes",
        "an unknown action_class means downstream action-rate breakdowns will silently mislabel or drop it",
        "confirm whether SoccerNet added new classes, or this is a parsing issue" if status != "PASS" else None,
    )
    if unknown:
        open_incident(
            conn, "staging_transform", "staging.action_event", "DATA_ISSUE",
            f"Unexpected action_class values found: {sorted(unknown)}",
            "MEDIUM", None, "action_class_distribution",
            "SoccerNet label schema drift or a parsing bug",
            "Analytics",
        )


def check_referential_integrity(conn):
    orphans = fetch_one(conn, """
        select count(*) from staging.action_event ae
        left join staging.match m on m.match_id = ae.match_id
        where m.match_id is null
    """)[0]
    status = "PASS" if orphans == 0 else "CRITICAL"
    record_check(
        conn, "action_event_match_referential_integrity", "staging.action_event", "match_id",
        status, "0 orphaned action_events", f"{orphans} orphaned",
        "orphaned events are invisible to every match-level rollup",
        "should be impossible given the foreign key -- investigate immediately if this fires" if status != "PASS" else None,
    )


def check_refresh_run_health(conn):
    rows = fetch_all(conn, """
        select distinct on (feed_id) feed_id, status, started_at
        from ops.refresh_run
        order by feed_id, started_at desc
    """)
    for feed_id, run_status, started_at in rows:
        status = "PASS" if run_status == "succeeded" else "CRITICAL"
        record_check(
            conn, "latest_refresh_run_succeeded", f"ops.refresh_run:{feed_id}", "status",
            status, "succeeded", run_status,
            f"a failed/stuck ingestion run for {feed_id} means staging may be running on stale or partial data",
            f"check ops.refresh_run.error_message for feed_id={feed_id}" if status != "PASS" else None,
        )
        if status != "PASS":
            open_incident(
                conn, feed_id, None, "PIPELINE_ISSUE",
                f"Latest refresh_run for {feed_id} did not succeed (status={run_status})",
                "HIGH", None, None,
                "check the ingestion script's error output for this feed",
                "Data Engineering",
            )


def main():
    conn = get_connection()
    print(f"Running real data-quality validation at {datetime.now(timezone.utc).isoformat()}")
    try:
        check_row_count_sanity(conn)
        check_match_field_completeness(conn)
        check_duplicate_matches(conn)
        check_action_class_drift(conn)
        check_referential_integrity(conn)
        check_refresh_run_health(conn)
    finally:
        conn.close()
    print("Validation complete. Results are in ops.validation_check; any "
          "finding above PASS also opened a row in ops.incident.")


if __name__ == "__main__":
    main()
