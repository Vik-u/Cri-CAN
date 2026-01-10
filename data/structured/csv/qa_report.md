# QA Report

- total_rows: 1196
- missing_bowler: 0
- missing_batsman: 0
- missing_result: 0
- invalid_ball_in_over: 0
- invalid_token_type: 0
- missing_ball_number: 0
- invalid_ball_number: 0
- missing_event_token: 0
- token_runs_mismatch: 0
- non_monotonic_over: 0
- non_monotonic_ball_index: 0

Notes:
- ball_in_over duplicates are expected for no-ball/wide cases in the source feed.
- RRR is only populated for the second innings; target is innings1 total + 1.
