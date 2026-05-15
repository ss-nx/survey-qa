#!/bin/bash
# Flags shell commands that would trigger real LLM API calls (and incur cost).
# Prompts for confirmation rather than blocking outright.

input=$(cat)
command=$(echo "$input" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null)

# Match commands that run the survey-qa tool against a real document
if echo "$command" | grep -qE 'survey.?qa|python.*cli\.py|uv run.*qa'; then
  echo '{
    "permission": "ask",
    "user_message": "This command will run the QA tool and may make real LLM API calls (cost: ~$0.005 for gpt-4o-mini). Continue?",
    "agent_message": "Hook: command may trigger paid LLM API calls via litellm. Confirm before proceeding."
  }'
  exit 0
fi

echo '{"permission": "allow"}'
exit 0
