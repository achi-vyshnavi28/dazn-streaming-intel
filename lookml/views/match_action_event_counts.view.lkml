view: match_action_event_counts {
  # Maps to analytics.match_action_event_counts -- one real row per SoccerNet
  # match (historical_broadcast only; football-data.org fixtures have no
  # play-by-play, so they never appear here -- see current_fixture_results
  # for those). This is the match-grain fact view; competition_action_rates
  # is the pre-aggregated competition/season-grain rollup of this same data.
  sql_table_name: analytics.match_action_event_counts ;;

  dimension: match_id {
    type: string
    sql: ${TABLE}.match_id ;;
    primary_key: yes
    description: "md5(raw game_id) -- stable synthetic key, not a SoccerNet-native id."
  }

  dimension: competition {
    type: string
    sql: ${TABLE}.competition ;;
  }

  dimension: season {
    type: string
    sql: ${TABLE}.season ;;
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
    timeframes: [date, week, month, quarter, year]
    sql: ${TABLE}.match_date ;;
  }

  dimension: source_type {
    type: string
    sql: ${TABLE}.source_type ;;
    description: "Always 'historical_broadcast' for this view -- see docs/DATA_PROVENANCE.md."
  }

  measure: match_count {
    type: count
    description: "Real count of distinct matches -- use this, not a count of a dimension, to avoid double-counting."
  }

  measure: total_goals {
    type: sum
    sql: ${TABLE}.goals ;;
  }

  measure: total_cards {
    type: sum
    sql: ${TABLE}.cards ;;
  }

  measure: total_corners {
    type: sum
    sql: ${TABLE}.corners ;;
  }

  measure: total_substitutions {
    type: sum
    sql: ${TABLE}.substitutions ;;
  }

  measure: total_shots {
    type: sum
    sql: ${TABLE}.shots ;;
  }

  measure: total_action_events {
    type: sum
    sql: ${TABLE}.total_action_events ;;
  }

  measure: avg_goals_per_match {
    type: average
    sql: ${TABLE}.goals ;;
    value_format_name: decimal_2
    description: "Row-weighted average computed directly from match-grain data -- an independent cross-check against competition_action_rates.avg_goals_per_match, which is itself already an average. The two should agree; if they don't, that's a real data-quality finding, not expected variance."
  }
}
