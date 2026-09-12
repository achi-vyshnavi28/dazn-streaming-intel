view: competition_action_rates {
  sql_table_name: analytics.competition_action_rates ;;

  dimension: competition {
    type: string
    sql: ${TABLE}.competition ;;
    description: "Real competition slug parsed from SoccerNet's game_id path, e.g. 'england_epl', 'europe_uefa-champions-league'."
  }

  dimension: season {
    type: string
    sql: ${TABLE}.season ;;
    description: "Real season string, e.g. '2016-2017', parsed from the same SoccerNet path."
  }

  dimension: primary_key {
    type: string
    sql: CONCAT(${TABLE}.competition, '|', ${TABLE}.season) ;;
    primary_key: yes
    hidden: yes
  }

  measure: match_count {
    type: sum
    sql: ${TABLE}.match_count ;;
    description: "Real count of historical_broadcast matches (SoccerNet) contributing to this competition/season row."
  }

  measure: avg_goals_per_match {
    type: average
    sql: ${TABLE}.avg_goals_per_match ;;
    value_format_name: decimal_2
    description: "Governed definition: ops.metric_definition key avg_goals_per_match. Average count of real SoccerNet 'Goal' action-spotting events per match."
  }

  measure: avg_cards_per_match {
    type: average
    sql: ${TABLE}.avg_cards_per_match ;;
    value_format_name: decimal_2
    description: "Governed definition: ops.metric_definition key avg_cards_per_match. Yellow + Red + Yellow->red card events per match, averaged."
  }

  measure: avg_corners_per_match {
    type: average
    sql: ${TABLE}.avg_corners_per_match ;;
    value_format_name: decimal_2
  }

  measure: avg_shots_per_match {
    type: average
    sql: ${TABLE}.avg_shots_per_match ;;
    value_format_name: decimal_2
  }

  measure: avg_action_events_per_match {
    type: average
    sql: ${TABLE}.avg_action_events_per_match ;;
    value_format_name: decimal_2
    description: "Governed definition: ops.metric_definition key avg_action_events_per_match. Proxy for match eventfulness across all 17 real SoccerNet action classes."
  }
}
