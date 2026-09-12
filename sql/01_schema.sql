create schema if not exists raw;
create schema if not exists staging;
create schema if not exists analytics;
create schema if not exists ops;

create table ops.source_feed_registry (
    feed_id             text primary key,
    display_name        text not null,
    provider            text not null,
    source_type         text not null check (source_type in
                            ('historical_broadcast','current_delayed','real_research','synthetic_derived')),
    access_method       text not null,
    license_notes        text,
    acquired_at          timestamptz,
    refresh_frequency    text,
    last_refreshed_at    timestamptz,
    validation_status    text default 'not_yet_validated'
                             check (validation_status in ('not_yet_validated','passing','warning','blocked')),
    notes                text
);

create table ops.refresh_run (
    run_id          bigint generated always as identity primary key,
    feed_id         text not null references ops.source_feed_registry(feed_id),
    started_at      timestamptz not null default now(),
    finished_at     timestamptz,
    rows_ingested   integer,
    status          text check (status in ('running','succeeded','failed')),
    error_message   text
);

create table ops.validation_check (
    check_id            bigint generated always as identity primary key,
    run_id              bigint references ops.refresh_run(run_id),
    check_name          text not null,
    dataset             text not null,
    field                text,
    status              text not null check (status in ('PASS','WARNING','CRITICAL')),
    expected            text,
    actual              text,
    detected_at         timestamptz not null default now(),
    impact              text,
    recommended_action  text
);

create table ops.incident (
    incident_id         bigint generated always as identity primary key,
    source               text not null,
    dataset              text,
    detected_at          timestamptz not null default now(),
    category             text not null check (category in
                             ('DATA_ISSUE','REPORTING_ISSUE','SOURCE_ISSUE','PIPELINE_ISSUE','BUSINESS_ANOMALY')),
    issue                text not null,
    severity             text not null check (severity in ('LOW','MEDIUM','HIGH','CRITICAL')),
    affected_records     integer,
    affected_metric      text,
    likely_cause         text,
    recommended_owner    text,
    status                text not null default 'OPEN' check (status in ('OPEN','INVESTIGATING','RESOLVED')),
    resolved_at           timestamptz
);

create table ops.metric_definition (
    metric_key       text primary key,
    display_name     text not null,
    definition_sql   text not null,
    owner            text not null default 'Analytics',
    description      text not null,
    updated_at       timestamptz not null default now()
);

create table raw.soccernet_action_events (
    raw_id           bigint generated always as identity primary key,
    game_id          text not null,
    competition      text,
    season           text,
    half             smallint,
    game_time_raw    text,
    action_class     text,
    team             text,
    visibility        text,
    loaded_at         timestamptz not null default now(),
    source_file       text
);

create table raw.football_data_fixtures (
    raw_id            bigint generated always as identity primary key,
    api_match_id      bigint not null,
    competition_code  text,
    season            text,
    utc_date_raw      text,
    status            text,
    home_team         text,
    away_team         text,
    home_score        integer,
    away_score        integer,
    fetched_at        timestamptz not null default now(),
    raw_payload       jsonb
);

create table raw.qoe_observations (
    raw_id          bigint generated always as identity primary key,
    content_ref      text,
    observation_ts   timestamptz,
    metric_name      text,
    metric_value     numeric,
    source_type      text not null check (source_type in ('real_research','synthetic_derived')),
    generation_method text,
    loaded_at        timestamptz not null default now()
);

create table raw.live_wild_qoe_scores (
    raw_id             bigint generated always as identity primary key,
    filename           text not null,
    base_content_id    text,
    distortion_code    char(1),
    resolution_tag     text,
    human_mos_score    numeric,
    loaded_at          timestamptz not null default now()
);

create table staging.match (
    match_id          text primary key,
    competition        text,
    season             text,
    home_team          text,
    away_team          text,
    match_date         date,
    source_type        text not null check (source_type in ('historical_broadcast','current_delayed')),
    feed_id            text not null references ops.source_feed_registry(feed_id)
);

create table staging.action_event (
    action_event_id   bigint generated always as identity primary key,
    match_id          text not null references staging.match(match_id),
    half              smallint not null check (half in (1,2)),
    game_time_seconds integer not null check (game_time_seconds >= 0),
    action_class      text not null,
    team              text,
    is_replayed       boolean not null default false,
    feed_id           text not null references ops.source_feed_registry(feed_id),
    unique (match_id, half, game_time_seconds, action_class, team)
);

create table staging.qoe_observation (
    qoe_id            bigint generated always as identity primary key,
    content_ref       text not null,
    observed_at       timestamptz not null,
    metric_name       text not null,
    metric_value      numeric not null,
    source_type       text not null check (source_type in ('real_research','synthetic_derived')),
    feed_id           text not null references ops.source_feed_registry(feed_id)
);

create table staging.qoe_video_sample (
    video_id           text primary key,
    base_content_id    text not null,
    distortion_type    text not null check (distortion_type in
                            ('reference','compression','interlacing','frame_drops','judder','flicker','aliasing')),
    resolution_tag      text,
    human_mos_score     numeric not null check (human_mos_score >= 0),
    feed_id             text not null references ops.source_feed_registry(feed_id)
);
