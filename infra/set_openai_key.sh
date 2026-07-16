#!/usr/bin/env bash
# One-time (or whenever you rotate it) step to store the real OpenAI API key
# in the Secrets Manager secret infra/template.yaml creates with a
# placeholder value. The key never becomes a CloudFormation parameter (which
# would persist it in the stack's parameter history), a file, or a shell
# history entry -- `read -s` takes it from stdin without echoing it and
# without it ever being a command-line argument.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f samconfig.toml ]]; then
  echo "No samconfig.toml found -- deploy the stack first (./deploy.sh --guided)." >&2
  exit 1
fi

STACK_NAME=$(grep -m1 '^stack_name' samconfig.toml | sed -E 's/stack_name[[:space:]]*=[[:space:]]*"([^"]+)"/\1/')
if [[ -z "$STACK_NAME" ]]; then
  echo "Could not determine stack name from samconfig.toml." >&2
  exit 1
fi

SECRET_ARN=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='OpenAIApiKeySecretArn'].OutputValue" --output text)
if [[ -z "$SECRET_ARN" || "$SECRET_ARN" == "None" ]]; then
  echo "Could not find OpenAIApiKeySecretArn in the stack outputs -- is the stack deployed?" >&2
  exit 1
fi

read -r -s -p "OpenAI API key: " OPENAI_KEY
echo
if [[ -z "$OPENAI_KEY" ]]; then
  echo "No key entered -- aborting." >&2
  exit 1
fi

aws secretsmanager put-secret-value --secret-id "$SECRET_ARN" \
  --secret-string "{\"OPENAI_API_KEY\":\"$OPENAI_KEY\"}" >/dev/null

echo "Stored. AdvisorFunction picks it up on its next cold start (redeploy to force one now)."
