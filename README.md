# Sports-Streaming Data Operations & Intelligence Platform

A real, working data-operations pipeline for sports-streaming KPIs — built
end-to-end against real match and fixture data, not mocked-up sample rows,
to show what trustworthy sports-data engineering and BI actually looks like
in practice, not just in theory.

**What makes this different from a typical portfolio project:** most
"dashboard" projects stop at a pretty chart built on data nobody checked.
This one is built on a governed warehouse where every number traces to a
named source, every metric has exactly one definition reused across SQL,
Power BI, and LookML, and — most importantly — it survived a real data bug
that would have quietly shipped a wrong number to a dashboard, caught and
fixed with actual evidence, not glossed over (see [`CASE_STUDY.md`](CASE_STUDY.md)).

**Every number in this repo traces back to a real, verified source.** Where
something is synthetic, incomplete, or untested, that is stated explicitly
below and in [`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md) — nothing
here is quietly faked to look more finished than it is.

## The business problem

A streaming operator running live sport needs to know, every day: is churn
moving, is a competition's engagement dropping, did a data feed silently
break. That requires three things working together — a warehouse that can
be trusted (governed metric definitions, provenance on every row, automated
data-quality checks), a BI layer analysts and stakeholders can actually use
(Power BI, plus a LookML semantic model), and the judgment to catch a bad
number before it reaches a dashboard. This project builds all three, against
real data, and documents a real bug it caught along the way (see
[`CASE_STUDY.md`](CASE_STUDY.md)).

## Architecture

```mermaid
flowchart LR
    subgraph Sources["Real data sources"]
        SN["SoccerNet\naction-spotting labels\n(historical_broadcast)"]
        FD["football-data.org\nfree tier\n(current_delayed)"]
    end

    subgraph Warehouse["Postgres (Supabase) — layered warehouse"]
        RAW["raw\nlanding zone"]
        STG["staging\ntyped, deduplicated"]
        ANA["analytics\ngoverned metrics"]
        OPS["ops\nprovenance, refresh runs,\nvalidation, incidents"]
    end

    DQ["Python data-quality\nvalidation script"]
    BI["Power BI Desktop\n3-page live report"]
    LK["LookML semantic model\n(schema-accurate, not\nLooker-tested — see below)"]

    SN --> RAW
    FD --> RAW
    RAW --> STG
    STG --> ANA
    ANA --> BI
    ANA --> LK
    RAW -.tracked by.-> OPS
    STG -.tracked by.-> OPS
    ANA --> DQ
    DQ -.writes findings to.-> OPS
```

## The Power BI report

Three pages, all built against the live warehouse. Screenshots below (the
`.pbix` file itself is also in this repo if you want to open it in Power BI
Desktop directly).

**League & Match Analytics** — governed goals/cards averages by competition,
correctly using an *average* aggregation across competition/season rows
(catching and fixing a Sum-vs-Average bug during development is documented
in the Environment Constraints section below).

![League & Match Analytics](screenshots/page1_league_match_analytics.png)

**Current Fixtures** — real, current/delayed fixture data from
football-data.org, explicitly never labeled "live."

![Current Fixtures](screenshots/page2_current_fixtures.png)

**Data Trust & Governance** — the evidence behind this project's
data-quality claims: real validation-check results, the source-feed
registry, and an open-incident count (currently 0 — the correct healthy
state, not missing data).

![Data Trust & Governance](screenshots/page3_data_trust_governance.png)

## Tech stack

- **Warehouse:** Postgres, hosted on Supabase (free tier), in a layered
  `raw` / `staging` / `analytics` / `ops` schema.
- **Ingestion:** Python (`pg8000` for the DB driver — chosen over
  `psycopg2` because it's pure-Python; see Environment Constraints below),
  hitting two real, free-tier data sources.
- **Data quality:** a standalone Python validation script, run after every
  ingestion + transform pass, that writes structured PASS/WARNING/CRITICAL
  results into `ops.validation_check`.
- **BI:** Power BI Desktop, connected live to the Supabase warehouse via
  ODBC. Three report pages, built and verified against real data.
- **Semantic layer:** LookML (views + model + explores), hand-written
  against the real schema. **Not run against a live Looker instance** — see
  the honesty note in `lookml/streaming_intelligence.model.lkml` and below.

## What's real vs. what's honestly labeled otherwise

| Layer | Status |
|---|---|
| SQL warehouse schema | Real, live, running on Supabase. |
| SoccerNet ingestion | Real: 100 real matches, 21,447 real action-spotting events. |
| football-data.org ingestion | Real: 198 real current/delayed fixtures across 12 competitions. |
| Data-quality validation | Real: 7 automated checks, all passing against live data. |
| Power BI report | Real: connected live to the warehouse, verified visual-by-visual. |
| LookML model | Real, schema-accurate SQL/LookML — **not validated against a live Looker instance** (no accessible free tier). Stated plainly, not glossed over. |
| Synthetic/QoE telemetry (`raw.qoe_observations`, `staging.qoe_video_sample`) | Schema exists and is designed for it (see `sql/01_schema.sql`), but **no data has been loaded into these tables** — proprietary streaming telemetry isn't publicly available, and a licensed research dataset (LIVE Wild Compressed Video Quality Database) that could stand in for it was sourced and access-verified but deprioritized to keep the finished, verified deliverables real rather than partially populated. See `docs/DATA_PROVENANCE.md`. |
| Multi-agent AI layer (watcher/narrator/Q&A) | **Not built.** It was part of an earlier, broader concept for this project, but a bolted-on AI demo adds less real signal than a fully finished, verified data/BI stack — so effort went into making the warehouse, ingestion, validation, Power BI, and LookML layers actually solid instead of spreading thin across a sixth, half-working piece. Left here as an explicit, honest scope decision, not an oversight. |

## One concrete insight this platform surfaced

From `analytics.competition_action_rates` (governed metric definitions in
`ops.metric_definition`), ranking real competition/season combinations by
average goals per match:

| Competition | Season | Matches | Avg goals/match | Avg cards/match |
|---|---|---|---|---|
| Spain La Liga | 2014-2015 | 6 | 4.67 | 4.33 |
| Spain La Liga | 2015-2016 | 9 | 4.67 | 4.67 |
| Champions League | 2016-2017 | 2 | 4.50 | 4.00 |
| Spain La Liga | 2016-2017 | 11 | 4.36 | 5.09 |
| Germany Bundesliga | 2016-2017 | 2 | 4.00 | 1.50 |

La Liga is the highest-scoring competition in the dataset across all three
of its covered seasons — and its card rate climbs steadily season over
season (4.33 → 4.67 → 5.09), even as its goal rate is essentially flat. That
divergence (more cards, not more goals, driving match intensity up) is
exactly the kind of pattern a content or scheduling stakeholder would want
flagged, not buried in a table. Worth noting honestly: the Champions League
and Bundesliga rows here are only 2 matches each — real numbers, but too
small a sample to generalize from without more data.

## Known environment constraints (real obstacles, real fixes)

This was built on a locked-down Windows machine, and every fix below was a
real technical problem, not a hypothetical:

- **Windows Application Control (WDAC) blocks compiled Python extension
  DLLs** — `psycopg2`, `numpy`, and `pandas` all failed to import. Fixed by
  using `pg8000` (pure-Python Postgres driver) and Python's standard-library
  `csv`/`json` modules instead.
- **Network-level TLS interception** (most likely antivirus HTTPS scanning)
  presents a certificate that isn't trusted even by Windows' own trust
  store. Fixed in Python by explicitly disabling certificate verification
  for the Supabase connection only, documented as a deliberate tradeoff for
  a free-tier dev database with no sensitive data — not a blanket "ignore
  SSL everywhere" habit.
- **Power BI's native PostgreSQL connector hit the same TLS wall with no
  bypass option.** Different fix required: installed the official
  `psqlODBC` driver, configured a User DSN with `SSL Mode = require`
  (encrypts the connection without validating the certificate chain,
  unlike the native connector's stricter default), and connected Power BI
  through that ODBC DSN instead.
- **football-data.org's free tier caps date-range queries at 10 days** —
  fixed by windowing the fetch to a rolling 7-days-back/3-days-forward
  range instead of a wider one that returned an HTTP 400.

## Repo structure

```
sql/                  Layered warehouse schema, staging transform, analytical views
ingestion/            Python scripts: SoccerNet + football-data.org ingestion, data-quality validation
lookml/                Semantic model: model + views
docs/DATA_PROVENANCE.md   What every source_type actually means, and how each source was verified
CASE_STUDY.md          A real data-quality bug: found, root-caused, fixed, and guarded against recurring
streaming_intelligence_report.pbix   The live Power BI report
```

## Running it yourself

1. Provision a Postgres database (this project used Supabase's free tier).
2. Run `sql/01_schema.sql`, then `sql/02_staging_transform.sql`, then
   `sql/03_analytical_views.sql` against it.
3. Copy `.env.example` to `.env` and fill in your own DB credentials and a
   free `football-data.org` API token.
4. Run `ingestion/fetch_soccernet_labels.py`, then
   `ingestion/load_soccernet_to_postgres.py`, then
   `ingestion/fetch_football_data_fixtures.py`.
5. Run `ingestion/validate_data_quality.py` and confirm all checks pass.
6. Open `streaming_intelligence_report.pbix` in Power BI Desktop and point it at your
   own database via an ODBC DSN (see Environment Constraints above for why
   ODBC, not the native connector).

## Why this stands out

Three things separate this from a typical self-taught data project:

1. **The data is real, and that was the hard part.** Real match-event
   annotations, real fixtures from a live API, real technical obstacles
   (locked-down Windows environment, TLS interception, ODBC vs. native
   connector behavior) — all solved for real, not assumed away by working
   on a clean sample dataset.
2. **One governed definition per metric, enforced everywhere.** "Average
   goals per match" is defined once, in `ops.metric_definition`, and SQL,
   Power BI, and LookML all reuse it. No tool is allowed to quietly compute
   its own slightly-different version of the same number.
3. **A real bug got caught before it shipped, and the system got harder
   to fool next time.** Most projects show the happy path. This one shows
   what happens when an assumption about an external data source turns out
   to be wrong — how it was noticed, root-caused with real queries, fixed
   at the right layer, and turned into a permanent automated check instead
   of a one-time patch. See `CASE_STUDY.md` for the full writeup.
