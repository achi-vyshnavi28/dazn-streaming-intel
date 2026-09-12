create or replace view analytics.match_action_event_counts as
select
    m.match_id,
    m.competition,
    m.season,
    m.home_team,
    m.away_team,
    m.match_date,
    m.source_type,
    count(*) filter (where ae.action_class = 'Goal')                                    as goals,
    count(*) filter (where ae.action_class in ('Yellow card','Red card','Yellow->red card')) as cards,
    count(*) filter (where ae.action_class = 'Corner')                                  as corners,
    count(*) filter (where ae.action_class = 'Substitution')                            as substitutions,
    count(*) filter (where ae.action_class in ('Shots on target','Shots off target'))   as shots,
    count(*)                                                                             as total_action_events
from staging.match m
join staging.action_event ae on ae.match_id = m.match_id
group by m.match_id, m.competition, m.season, m.home_team, m.away_team, m.match_date, m.source_type;

create or replace view analytics.competition_action_rates as
select
    competition,
    season,
    count(distinct match_id)                          as match_count,
    round(avg(goals)::numeric, 2)                      as avg_goals_per_match,
    round(avg(cards)::numeric, 2)                      as avg_cards_per_match,
    round(avg(corners)::numeric, 2)                    as avg_corners_per_match,
    round(avg(shots)::numeric, 2)                      as avg_shots_per_match,
    round(avg(total_action_events)::numeric, 2)        as avg_action_events_per_match
from analytics.match_action_event_counts
group by competition, season
order by competition, season;

create or replace view analytics.current_fixture_results as
select
    m.match_id,
    m.competition,
    m.home_team,
    m.away_team,
    m.match_date,
    f.status,
    f.home_score,
    f.away_score,
    f.fetched_at
from staging.match m
join raw.football_data_fixtures f
    on m.match_id = 'fd_' || f.api_match_id::text
where m.source_type = 'current_delayed';

insert into ops.metric_definition (metric_key, display_name, definition_sql, owner, description)
values
(
    'avg_goals_per_match',
    'Average Goals per Match',
    'select competition, season, avg_goals_per_match from analytics.competition_action_rates',
    'Analytics',
    'Average number of real Goal action-spotting events per match, by competition and season. Source: SoccerNet historical_broadcast labels.'
),
(
    'avg_cards_per_match',
    'Average Cards per Match',
    'select competition, season, avg_cards_per_match from analytics.competition_action_rates',
    'Analytics',
    'Average number of yellow/red/second-yellow card events per match, by competition and season. Source: SoccerNet historical_broadcast labels.'
),
(
    'avg_action_events_per_match',
    'Average Action Events per Match',
    'select competition, season, avg_action_events_per_match from analytics.competition_action_rates',
    'Analytics',
    'Average count of all real action-spotting events (across the 17 SoccerNet classes) per match -- a proxy for match eventfulness.'
),
(
    'current_fixture_count_by_competition',
    'Current Fixtures by Competition (±10 day window)',
    'select competition, count(*) as fixture_count from analytics.current_fixture_results group by competition order by fixture_count desc',
    'Analytics',
    'Count of real, current_delayed fixtures from football-data.org''s free tier within the ingested ~10-day window, by competition. Free tier only -- not live scores.'
)
on conflict (metric_key) do update set
    definition_sql = excluded.definition_sql,
    description    = excluded.description,
    updated_at     = now();

select
    (select count(*) from analytics.match_action_event_counts) as match_action_rows,
    (select count(*) from analytics.competition_action_rates)  as competition_rate_rows,
    (select count(*) from analytics.current_fixture_results)   as current_fixture_rows,
    (select count(*) from ops.metric_definition)                as metric_definitions;
