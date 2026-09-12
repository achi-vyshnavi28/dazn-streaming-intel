view: validation_check {
  # Maps to ops.validation_check -- real, structured data-quality check
  # results (see ingestion/validate_data_quality.py). This is what backs
  # the "attention to detail and data quality" line in the JD with actual
  # evidence, in both Power BI and here, not a claim in a README.
  sql_table_name: ops.validation_check ;;

  dimension: check_id {
    type: number
    sql: ${TABLE}.check_id ;;
    primary_key: yes
  }

  dimension: check_name {
    type: string
    sql: ${TABLE}.check_name ;;
  }

  dimension: dataset {
    type: string
    sql: ${TABLE}.dataset ;;
  }

  dimension: status {
    type: string
    sql: ${TABLE}.status ;;
    description: "One of PASS / WARNING / CRITICAL -- see ingestion/validate_data_quality.py for the exact real checks that produce this."
  }

  dimension: expected {
    type: string
    sql: ${TABLE}.expected ;;
  }

  dimension: actual {
    type: string
    sql: ${TABLE}.actual ;;
  }

  dimension_group: detected {
    type: time
    timeframes: [raw, date, time]
    sql: ${TABLE}.detected_at ;;
  }

  measure: check_count {
    type: count
  }

  measure: pass_count {
    type: count
    filters: [status: "PASS"]
  }

  measure: critical_count {
    type: count
    filters: [status: "CRITICAL"]
    description: "Should be 0 in a healthy pipeline. Any non-zero value here is a real problem, not a display quirk."
  }
}

view: incident {
  # Maps to ops.incident -- opened automatically by
  # ingestion/validate_data_quality.py whenever a check goes above PASS.
  # Empty (0 rows) as of the last real run -- that's the correct healthy
  # state, not missing data.
  sql_table_name: ops.incident ;;

  dimension: incident_id {
    type: number
    sql: ${TABLE}.incident_id ;;
    primary_key: yes
  }

  dimension: source {
    type: string
    sql: ${TABLE}.source ;;
  }

  dimension: category {
    type: string
    sql: ${TABLE}.category ;;
  }

  dimension: severity {
    type: string
    sql: ${TABLE}.severity ;;
  }

  dimension: status {
    type: string
    sql: ${TABLE}.status ;;
  }

  dimension: issue {
    type: string
    sql: ${TABLE}.issue ;;
  }

  measure: open_incident_count {
    type: count
    filters: [status: "OPEN"]
    description: "The headline number for a data-trust dashboard tile. Real value as of the last run: 0."
  }
}

view: source_feed_registry {
  # Maps to ops.source_feed_registry -- the provenance backbone. Every
  # feed_id referenced anywhere in staging/analytics traces back to exactly
  # one row here, matching docs/DATA_PROVENANCE.md.
  sql_table_name: ops.source_feed_registry ;;

  dimension: feed_id {
    type: string
    sql: ${TABLE}.feed_id ;;
    primary_key: yes
  }

  dimension: display_name {
    type: string
    sql: ${TABLE}.display_name ;;
  }

  dimension: provider {
    type: string
    sql: ${TABLE}.provider ;;
  }

  dimension: source_type {
    type: string
    sql: ${TABLE}.source_type ;;
    description: "One of historical_broadcast / current_delayed / real_research / synthetic_derived -- the only four values this project uses, see docs/DATA_PROVENANCE.md."
  }

  dimension: validation_status {
    type: string
    sql: ${TABLE}.validation_status ;;
  }

  dimension_group: acquired {
    type: time
    timeframes: [raw, date]
    sql: ${TABLE}.acquired_at ;;
  }

  measure: feed_count {
    type: count
  }
}
