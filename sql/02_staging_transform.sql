-- ============================================================================
-- STAGING transform: raw -> staging
--
-- Idempotent by design -- safe to re-run after every ingestion run (upserts
-- staging.match on its natural key, and staging.action_event has a unique
-- constraint with ON CONFLICT DO NOTHING), so running this twice never
-- creates duplicate staging rows.
--
-- game_id's real, verified shape (confirmed against actual Supabase data,
-- not assumed):
--   <competition_slug>\<season>\YYYY-MM-DD - HH-MM HomeTeam <hs> - <as> AwayTeam
-- e.g. "england_epl\2016-2017\2016-10-02 - 18-30 Burnley 0 - 1 Arsenal"
--
-- competition/season are pulled from THIS path, not from
-- raw.soccernet_action_events.competition/.season -- those columns are
-- null for every real row, because SoccerNet's actual Labels-v2.json has
-- no top-level "competition"/"season" keys (confirmed against real data:
-- fetch_soccernet_labels.py's data.get("competition") returns None for
-- every game). That info only ever existed in the folder path. Known,
-- documented ingestion-script bug -- worked around here rather than
-- re-downloading, since the path already carries real, correct values.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- staging.match, historical_broadcast rows (from SoccerNet)
-- ---------------------------------------------------------------------------
insert into staging.match (match_id, competition, season, home_team, away_team, match_date, source_type, feed_id)
select
    md5(r.game_id) as match_id,
    split_part(r.game_id, '\', 1) as competition,
    split_part(r.game_id, '\', 2) as season,
    parsed.m[3] as home_team,
    parsed.m[6] as away_team,
    to_date(parsed.m[1], 'YYYY-MM-DD') as match_date,
    'historical_broadcast' as source_type,
    'soccernet_labels_v2' as feed_id
from (
    select distinct game_id
    from raw.soccernet_action_events
) r
cross join lateral (
    select regexp_match(
        -- last path segment after the final backslash
        reverse(split_part(reverse(r.game_id), '\', 1)),
        '^(\d{4}-\d{2}-\d{2}) - (\d{2}-\d{2}) (.+?) (\d+) - (\d+) (.+)$'
    ) as m
) parsed
on conflict (match_id) do update set
    competition = excluded.competition,
    season      = excluded.season,
    home_team   = excluded.home_team,
    away_team   = excluded.away_team,
    match_date  = excluded.match_date;

-- ---------------------------------------------------------------------------
-- staging.match, current_delayed rows (from football-data.org)
-- ---------------------------------------------------------------------------
insert into staging.match (match_id, competition, season, home_team, away_team, match_date, source_type, feed_id)
select distinct
    'fd_' || f.api_match_id::text as match_id,
    f.competition_code,
    f.season,
    f.home_team,
    f.away_team,
    (f.utc_date_raw::timestamptz)::date as match_date,
    'current_delayed' as source_type,
    'football_data_org' as feed_id
from raw.football_data_fixtures f
on conflict (match_id) do update set
    competition = excluded.competition,
    season      = excluded.season,
    home_team   = excluded.home_team,
    away_team   = excluded.away_team,
    match_date  = excluded.match_date;

-- ---------------------------------------------------------------------------
-- staging.action_event (SoccerNet only -- football-data.org's free tier has
-- no play-by-play, only fixtures/results)
-- ---------------------------------------------------------------------------
insert into staging.action_event (match_id, half, game_time_seconds, action_class, team, is_replayed, feed_id)
select
    md5(r.game_id) as match_id,
    r.half,
    split_part(r.game_time_raw, ':', 1)::int * 60
        + split_part(r.game_time_raw, ':', 2)::int as game_time_seconds,
    r.action_class,
    r.team,
    false as is_replayed,
    'soccernet_labels_v2' as feed_id
from raw.soccernet_action_events r
where r.half is not null
  and r.game_time_raw ~ '^\d+:\d+$'   -- defensive: skip malformed timestamps rather than crash
on conflict (match_id, half, game_time_seconds, action_class, team) do nothing;

-- ---------------------------------------------------------------------------
-- Quick sanity read after running the above -- not part of the transform,
-- just a manual check. Expect ~ a few hundred distinct matches and 21447
-- (minus any that failed the game_time_raw filter) action events.
-- ---------------------------------------------------------------------------
select
    (select count(*) from staging.match) as staging_match_rows,
    (select count(*) from staging.match where home_team is null) as staging_match_unparsed,
    (select count(*) from staging.action_event) as staging_action_event_rows;
