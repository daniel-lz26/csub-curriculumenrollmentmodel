#!/usr/bin/env bash
# Build + deploy the API Gateway/Lambda/S3 stack, then publish the data the
# deployed Lambda and frontend need (roadmap_advisor.json, frontend/web/*).
#
# First run ever: `./deploy.sh --guided` (walks you through stack name/region
# and writes samconfig.toml), then run `./infra/set_openai_key.sh` once to
# store the real OpenAI key (the template only creates a placeholder secret
# -- see infra/template.yaml). Every run after that: `./deploy.sh`.
#
# `.samignore` is NOT read by `sam build` (verified against SAM CLI 1.163.0 /
# aws-lambda-builders 1.65.0 — neither package references "samignore"; it
# only ever applied to the legacy raw-zip `sam package` flow). CodeUri is the
# repo root (so the Lambda can import the sibling `advisor`/`mining`
# packages unchanged), so `sam build`'s CopySource step copies the entire
# repo verbatim — including the gitignored 130MB+ of `data/raw` source
# files and test directories. That alone pushes the function past Lambda's
# 250MB unzipped limit. This script prunes those paths from the build output
# before deploying, since there's no supported exclude mechanism for the
# standard Python/pip build. data/output is pruned too: the roadmap-advisor
# cache is read from S3 at call time (see api/handlers/_data.py), not bundled.
set -euo pipefail
cd "$(dirname "$0")"

sam build --template-file template.yaml

for fn in AdvisorFunction; do
  rm -rf \
    ".aws-sam/build/$fn/data/raw" \
    ".aws-sam/build/$fn/data/output" \
    ".aws-sam/build/$fn/api/tests" \
    ".aws-sam/build/$fn/mining/tests" \
    ".aws-sam/build/$fn/advisor/tests" \
    ".aws-sam/build/$fn/frontend" \
    ".aws-sam/build/$fn/contextv67" \
    ".aws-sam/build/$fn/.pytest_cache" \
    ".aws-sam/build/$fn/.claude" \
    ".aws-sam/build/$fn/.kiro" \
    ".aws-sam/build/$fn/.git"
done

sam deploy "$@"

# ---- Publish data + frontend to the buckets the stack just created --------
# Only runs after a deploy that has a saved config (so we know the stack
# name). If you passed a one-off --stack-name instead of using --guided,
# rerun the two `aws s3` commands below by hand with your own bucket names
# (see the stack Outputs in the CloudFormation console or `sam deploy` output).
if [[ ! -f samconfig.toml ]]; then
  echo "No samconfig.toml found -- skipping S3 publish steps (see comment in this script)."
  exit 0
fi

STACK_NAME=$(grep -m1 '^stack_name' samconfig.toml | sed -E 's/stack_name[[:space:]]*=[[:space:]]*"([^"]+)"/\1/')
if [[ -z "$STACK_NAME" ]]; then
  echo "Could not determine stack name from samconfig.toml -- skipping S3 publish steps."
  exit 0
fi

_output() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

API_URL=$(_output ApiUrl)
DATA_BUCKET=$(_output DataBucketName)
FRONTEND_BUCKET=$(_output FrontendBucketName)
FRONTEND_URL=$(_output FrontendWebsiteUrl)

echo "Stack outputs: ApiUrl=$API_URL DataBucket=$DATA_BUCKET FrontendBucket=$FRONTEND_BUCKET"

cd ..

# 1. Roadmap-advisor cache -> DataBucket. AdvisorFunction reads this at
#    request time (see api/handlers/_data.py) instead of it being bundled
#    into the Lambda zip. The source xlsx is small, so this always
#    regenerates rather than only rebuilding when missing.
python3 -m advisor.build_data
aws s3 cp data/output/roadmap_advisor.json "s3://$DATA_BUCKET/roadmap_advisor.json"

# 2. Static frontend -> FrontendBucket. API_BASE_URL is patched into a
#    throwaway copy of config.js so the repo's own copy stays blank (offline
#    demo mode for local `python -m http.server` runs -- see
#    frontend/web/README.md).
TMP_FRONTEND=$(mktemp -d)
trap 'rm -rf "$TMP_FRONTEND"' EXIT
cp -r frontend/web/. "$TMP_FRONTEND/"
sed -E "s#const API_BASE_URL = \"[^\"]*\";#const API_BASE_URL = \"${API_URL%/}\";#" \
  frontend/web/config.js > "$TMP_FRONTEND/config.js"
rm -rf "$TMP_FRONTEND/README.md" "$TMP_FRONTEND/__pycache__"
aws s3 sync "$TMP_FRONTEND/" "s3://$FRONTEND_BUCKET/" --delete

echo ""
echo "Deployed."
echo "  Frontend:  $FRONTEND_URL"
echo "  API:       $API_URL"
echo ""
echo "If you haven't yet, run ./set_openai_key.sh once to store the real OpenAI key"
echo "(the secret currently holds a placeholder -- /advisor will 503 until it's set)."
