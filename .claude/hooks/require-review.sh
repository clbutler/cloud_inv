#!/bin/bash
# PreToolUse hook for Bash: code only reaches main after /code-review.
#
#   As a hook (no arguments): blocks merges and pushes to main unless the changes have been reviewed.
#   require-review.sh --mark: run after /code-review to record the review, which lets the merge through.
#
# A review is tied to a fingerprint of everything the branch would add to main, so any change made
# after the review needs a fresh one.

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}" || exit 0
reviewed_file=".claude/last-reviewed"
fingerprint=$(git diff origin/main...HEAD | shasum | cut -d' ' -f1)
has_changes=$([ -n "$(git diff origin/main...HEAD)" ] && echo true || echo false)
branch=$(git branch --show-current 2>/dev/null)

if [ "$1" = "--mark" ]; then
  echo "$fingerprint" > "$reviewed_file"
  echo "Review recorded for $branch ($fingerprint)"
  exit 0
fi

input=$(cat)                                                  # the JSON Claude Code sends the hook
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

puts_code_on_main=false
if printf '%s' "$cmd" | grep -Eq 'gh pr merge|git merge'; then
  puts_code_on_main=true                                      # merging a pull request or a branch
elif printf '%s' "$cmd" | grep -q 'git push' && { printf '%s' "$cmd" | grep -wq 'main' || [ "$branch" = "main" ]; }; then
  puts_code_on_main=true                                      # pushing to main, or pushing while on main
fi

log() {
  printf '%s' "$input" | jq -c --arg branch "$branch" --arg decision "$1" \
    '{time: (now | todate), branch: $branch, decision: $decision, command: .tool_input.command}' \
    >> ".claude/hook-log.jsonl"
}

if [ "$puts_code_on_main" = false ]; then
  exit 0                                                      # exit 0 with no output = let the command run
fi
if [ "$has_changes" = false ]; then
  log "allowed: nothing new for main"
  exit 0
fi
if [ "$fingerprint" = "$(cat "$reviewed_file" 2>/dev/null)" ]; then
  log "allowed: reviewed"
  exit 0
fi

log "blocked: not reviewed"
# the reply that stops the command: Claude Code cancels it and shows Claude the reason
jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: "This command puts code on main, and these changes have not been reviewed. Run /code-review on this branch, fix or report any findings, then record the review with .claude/hooks/require-review.sh --mark and try again."
  }
}'
exit 0
