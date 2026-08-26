#!/bin/sh

# Claude sends one JSON object on stdin. Keep this event-driven and cheap: one
# jq process plus one read-only git lookup, with no timer or background process.
input=$(cat)
cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // "."')
branch=$(git -C "$cwd" branch --show-current 2>/dev/null || true)

printf '%s' "$input" | jq -r --arg branch "$branch" '
  def money:
    (. * 100 | round) as $cents
    | ($cents / 100 | floor | tostring) as $whole
    | ($cents % 100 | tostring) as $fraction
    | "$" + $whole + "." +
      (if ($fraction | length) == 1 then "0" + $fraction else $fraction end);
  def elapsed:
    (. / 1000 | floor) as $seconds
    | (($seconds / 60 | floor) | tostring) + "m" +
      (($seconds % 60) | tostring) + "s";
  (.model.display_name // .model.id // "Claude") as $model
  | (.effort.level // empty) as $effort
  | (.workspace.project_dir // .workspace.current_dir // .cwd // ".") as $path
  | ($path | split("/") | map(select(length > 0)) | last // "/") as $project
  | (.context_window.remaining_percentage // null) as $remaining
  | (.cost.total_cost_usd // 0) as $cost
  | (.cost.total_duration_ms // 0) as $duration
  | [
      ($model + (if $effort == "" then "" else "/" + $effort end)),
      ($project + (if $branch == "" then "" else "@" + $branch end)),
      (if $remaining == null then "ctx --" else "ctx " + (($remaining | floor) | tostring) + "% left" end),
      ($cost | money),
      ($duration | elapsed)
    ]
  | join(" · ")
'
