# Knowledge Graph Schema (match KG)

## nodes.csv
- node_id: unique node id (match:, innings:, over:, ball:, team:, player:, event:, phase:)
- node_type: match|innings|over|ball|team|player|event_type|phase
- name: human-readable label
- match_id: match id (where applicable)
- innings_index: innings number (where applicable)
- over: over number (where applicable)
- ball_in_over: ball number inside the over (where applicable)

## edges.csv
- source_id: node_id for source
- relation: has_innings|has_over|has_ball|batting_team|has_player|batsman|bowler|event_type|phase
- target_id: node_id for target

## ball_state.csv
- ball_id: links to nodes.csv ball node
- match_id: match id
- innings_index: innings number
- over: over number (0-based, raw from source)
- ball_in_over: ball number within over
- ball_number: raw over.ball string
- ball_index: sequential id in source
- batting_team: batting team short name
- batsman: striker name
- bowler: bowler name
- event_type: run|dot|wicket|extra|boundary
- event_token: raw token (e.g., 4, W, •)
- result_raw: raw ball result string
- is_wicket: true/false
- is_boundary: true/false
- bat_runs: runs off the bat
- extras_runs: extras on the ball
- innings_runs: total runs after this ball
- innings_wickets: total wickets after this ball
- innings_overs: overs completed after this ball
- crr: current run rate
- target_runs: target runs (if chase)
- runs_remaining: runs remaining (if chase)
- balls_remaining: balls remaining (if chase)
- rrr: required run rate
- phase: powerplay|middle|death
