# Structured Commentary Schema

## balls.csv
- match_id: file stem
- source_file: original txt file name
- ball_index: sequential id per file
- innings_index: 1-based inning index within file
- batting_team: inferred from score lines (e.g., SL, IND)
- over: over number
- ball_in_over: ball number within over
- ball_number: raw over.ball string
- event_token: raw token line (e.g., •, 4, 1lb, W)
- token_runs: numeric runs parsed from token
- token_type: run|dot|wicket|nb|lb|b|w
- bowler: parsed bowler name
- batsman: parsed striker name
- result_raw: raw result text after the comma
- is_wicket: true/false derived from token or result text
- commentary: extra lines between this ball and next event

## meta.csv
- match_id: file stem
- source_file: original txt file name
- innings_index: 1-based inning index within file
- meta_type: innings_header|over_summary|meta
- over: over number for over_summary rows
- text: raw meta block or narrative line
