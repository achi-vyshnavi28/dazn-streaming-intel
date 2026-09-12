view: current_fixture_results {
  # Maps to analytics.current_fixture_results -- the current_delayed layer
  # (football-data.org free tier). Real fixtures/results, explicitly NOT
  # live scores -- football-data.org's free tier delays data, and this
  # project never labels it "live" anywhere, including here.
  sql_table_name: analytics.current_fixture_results ;;

  dimension: match_id {
    type: string
    sql: ${TABLE}.match_id ;;
    primary_key: yes
  }

  dimension: competition {
    type: string
    sql: ${TABLE}.competition ;;
    description: "football-data.org competition code, e.g. 'PL', 'BL1', 'CL' -- the free tier's 12 covered competitions."
  }

  dimension: home_team {
    type: string
    sql: ${TABLE}.home_team ;;
  }

  dimension: away_team {
    type: string
    sql: ${TABLE}.away_team ;;
  }

  dimension_group: match {
    type: time
    timeframes: [date, week, month]
    sql: ${TABLE}.match_date ;;
  }

  dimension: status {
    type: string
    sql: ${TABLE}.status ;;
    description: "Real match status from football-data.org, e.g. SCHEDULED, FINISHED."
  }

  dimension: home_score {
    type: number
    sql: ${TABLE}.home_score ;;
  }

  dimension: away_score {
    type: number
    sql: ${TABLE}.away_score ;;
  }

  dimension_group: fetched {
    type: time
    timeframes: [raw, date, time]
    sql: ${TABLE}.fetched_at ;;
    description: "When this row was actually pulled from the API -- the real freshness signal for this current_delayed data."
  }

  measure: fixture_count {
    type: count
    description: "Governed definition: ops.metric_definition key current_fixture_count_by_competition."
  }

  measure: finished_count {
    type: count
    filters: [status: "FINISHED"]
  }
}
