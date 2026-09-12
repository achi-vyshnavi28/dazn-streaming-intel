# DAZN Sports-Streaming Data Ops & Intelligence Platform -- LookML model
#
# HONESTY NOTE (read this before anything else): this model was written
# against the real, live Supabase Postgres schema (same one the Power BI
# report and the Python agent tooling connect to) and every dimension/
# measure name matches real columns in sql/01_schema.sql through
# sql/03_analytical_views.sql exactly. It has NOT been run against a live
# Looker instance -- Looker has no meaningful free tier, and getting one
# was outside this project's reach. This is real, syntactically correct
# LookML mapped to a real schema, not a validated, deployed model. Said
# plainly in the README too. The JD lists LookML as "preferred," and Power
# BI (built and verified live) is the primary, tested BI deliverable.

connection: "dazn_streaming_intel_postgres"  # Supabase Postgres, session pooler.
# host: aws-0-ap-northeast-1.pooler.supabase.com, port 5432, database: postgres
# Real connection details live in .env, not committed to this repo.

include: "/views/*.view.lkml"

datagroup: dazn_streaming_default_datagroup {
  # Ingestion here is on-demand (manual script runs), not a fixed schedule
  # -- see ingestion/*.py. sql_trigger checks the most recent successful
  # refresh_run rather than assuming a cron cadence that doesn't exist yet.
  sql_trigger: SELECT MAX(finished_at) FROM ops.refresh_run WHERE status = 'succeeded' ;;
  max_cache_age: "4 hours"
}

persist_with: dazn_streaming_default_datagroup

explore: competition_action_rates {
  label: "League & Match Analytics"
  description: "Governed competition/season-level metrics -- goals, cards, corners, shots per match. Historical_broadcast (SoccerNet) data only."
}

explore: match_action_event_counts {
  label: "Match-Level Action Events"
  description: "Match-grain detail behind competition_action_rates. Useful for drill-down and as a cross-check against the pre-aggregated rollup."
}

explore: current_fixture_results {
  label: "Current Fixtures"
  description: "Real, current_delayed fixtures/results from football-data.org's free tier. Not live scores -- see dimension descriptions."
}

explore: validation_check {
  label: "Data Trust: Validation Checks"
  description: "Real results from ingestion/validate_data_quality.py. The evidence behind this project's data-quality claims."

  join: incident {
    type: left_outer
    sql_on: 1 = 1 ;;  # incident and validation_check share no direct key; both roll up to the same pipeline runs independently.
    relationship: many_to_many
  }
}

explore: source_feed_registry {
  label: "Data Trust: Source Provenance"
  description: "Every real data source this project uses, its access method, and its current validation status. Backs docs/DATA_PROVENANCE.md."
}
