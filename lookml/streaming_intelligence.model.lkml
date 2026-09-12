connection: "streaming_intelligence_postgres"

include: "/views/*.view.lkml"

datagroup: streaming_intelligence_default_datagroup {
  sql_trigger: SELECT MAX(finished_at) FROM ops.refresh_run WHERE status = 'succeeded' ;;
  max_cache_age: "4 hours"
}

persist_with: streaming_intelligence_default_datagroup

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
    sql_on: 1 = 1 ;;
    relationship: many_to_many
  }
}

explore: source_feed_registry {
  label: "Data Trust: Source Provenance"
  description: "Every real data source this project uses, its access method, and its current validation status. Backs docs/DATA_PROVENANCE.md."
}
