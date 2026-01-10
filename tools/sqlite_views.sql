DROP VIEW IF EXISTS ball_summary;
DROP VIEW IF EXISTS wickets;
DROP VIEW IF EXISTS boundaries;
DROP VIEW IF EXISTS extras;
DROP VIEW IF EXISTS over_summaries;
DROP VIEW IF EXISTS over_totals;
DROP VIEW IF EXISTS partnerships;

CREATE VIEW ball_summary AS
SELECT
    match_id,
    source_file,
    innings_index,
    batting_team,
    over,
    ball_in_over,
    ball_number,
    event_token,
    token_runs,
    token_type,
    bowler,
    batsman,
    result_raw,
    is_wicket,
    commentary
FROM balls;

CREATE VIEW wickets AS
SELECT *
FROM balls
WHERE is_wicket = 'true' OR event_token = 'W' OR lower(result_raw) LIKE '% out%';

CREATE VIEW boundaries AS
SELECT *
FROM balls
WHERE token_runs >= 4;

CREATE VIEW extras AS
SELECT *
FROM balls
WHERE token_type IN ('b','lb','nb','w');

CREATE VIEW over_summaries AS
SELECT
    match_id,
    source_file,
    innings_index,
    over,
    text AS summary
FROM meta
WHERE meta_type = 'over_summary';

CREATE VIEW over_totals AS
SELECT
    match_id,
    source_file,
    innings_index,
    over,
    COUNT(*) AS balls,
    SUM(token_runs) AS runs,
    SUM(CASE WHEN token_runs >= 4 THEN 1 ELSE 0 END) AS boundaries,
    SUM(CASE WHEN is_wicket = 'true' OR event_token = 'W' THEN 1 ELSE 0 END) AS wickets
FROM balls
GROUP BY match_id, source_file, innings_index, over;

CREATE VIEW partnerships AS
WITH ordered AS (
    SELECT
        match_id,
        source_file,
        innings_index,
        over,
        ball_in_over,
        ball_index,
        batsman,
        token_runs,
        CASE WHEN is_wicket = 'true' OR event_token = 'W' THEN 1 ELSE 0 END AS wicket_flag,
        SUM(CASE WHEN is_wicket = 'true' OR event_token = 'W' THEN 1 ELSE 0 END)
            OVER (PARTITION BY match_id, innings_index ORDER BY over, ball_in_over, ball_index) AS wicket_no
    FROM balls
)
SELECT
    match_id,
    source_file,
    innings_index,
    wicket_no AS partnership_index,
    group_concat(DISTINCT batsman) AS batsmen,
    COUNT(*) AS balls,
    SUM(token_runs) AS runs
FROM ordered
GROUP BY match_id, source_file, innings_index, wicket_no
ORDER BY match_id, innings_index, wicket_no;
