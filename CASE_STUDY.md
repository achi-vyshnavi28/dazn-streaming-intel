# Case Study: A Silent Data-Quality Bug, Found and Fixed

This is a worked example of a real bug that happened while building this
platform — not a staged demo. It's here because catching exactly this kind
of failure, quietly, before it reaches a dashboard, is the job.

## The setup

The warehouse ingests real match-event data from SoccerNet's action-spotting
labels (`Labels-v2.json`) into `raw.soccernet_action_events`, which then
feeds a staging layer (`staging.match`) and a governed analytical rollup
(`analytics.competition_action_rates` — average goals/cards/corners/shots
per match, grouped by competition and season).

## What went wrong

`ingestion/fetch_soccernet_labels.py` originally populated `competition` and
`season` on each raw row using `data.get("competition")` and
`data.get("season")` — reading them as top-level keys in SoccerNet's JSON.

They aren't there. SoccerNet only encodes competition and season in the
**folder path** each label file lives under (e.g.
`england_epl/2016-2017/2016-08-13 - ... /Labels-v2.json`), not inside the
JSON payload itself. `data.get()` returned `None` for every single one of
21,447 rows, silently. No exception, no warning — just nulls, all the way
through.

## Where it surfaced

Nothing looked wrong until the analytical layer. The real dataset spans 100
matches across 17 distinct competition/season combinations. After the
staging transform ran, `analytics.competition_action_rates` — which groups
by `(competition, season)` — had collapsed to **1 row** instead of 17. Every
match had folded into a single `(NULL, NULL)` group.

That's the kind of failure that's easy to miss in a chart: a bar chart with
one bar instead of seventeen doesn't throw an error, it just looks like a
simpler chart. It would have shipped clean to Power BI if nobody checked the
row count against what the source data actually contains.

## Root-causing it

Two queries, run directly against the warehouse, isolated where the nulls
actually originated:

```sql
select distinct competition, season from staging.match;
-- returned a single blank row

select distinct competition, season from raw.soccernet_action_events;
-- also blank -- confirms the problem is upstream of staging, in ingestion
```

That ruled out the staging transform as the cause and pointed straight at
the ingestion script's assumption about the JSON shape.

## The fix

Rather than re-running ingestion against a patched script (the raw layer
already had the real, correctly-timestamped event data — only the
competition/season labels were wrong, and they're fully recoverable from the
folder path that's already embedded in `game_id`), the fix was made at the
staging-transform layer in `sql/02_staging_transform.sql`: parse
`competition` and `season` directly out of `game_id`'s path instead of
trusting the broken raw columns.

```sql
split_part(r.game_id, '\', 1) as competition,
split_part(r.game_id, '\', 2) as season,
```

After the fix: `analytics.competition_action_rates` correctly produced all
17 real competition/season rows.

## Making sure it can't happen again quietly

A bug like this — a silent `NULL` from a wrong assumption about an external
API/file shape — doesn't announce itself. The fix that matters isn't just
patching this one instance; it's making the pipeline unable to ship a
regression of the same class without being caught automatically.

`ingestion/validate_data_quality.py`'s `check_match_field_completeness()`
check was extended to null-check `competition` and `season` alongside the
fields it already checked (`home_team`, `away_team`, `match_date`). If this
class of bug reappears — a future feed, a future field, the same "assumed a
key exists in the payload" mistake — the validation run fails loudly instead
of quietly degrading a downstream rollup.

## Why this is the centerpiece of this project, not a footnote

Anyone can build a pipeline that works when the input is well-behaved.
Real attention to detail and data quality looks like this in practice: not
writing code that's correct on the happy path, but noticing when a real
result (1 row instead of 17) is implausible, tracing it to its actual root
cause with real queries instead of guessing, fixing it at the right layer,
and then hardening the system so the same class of failure gets caught
automatically next time instead of relying on someone noticing a
suspiciously small chart again.
