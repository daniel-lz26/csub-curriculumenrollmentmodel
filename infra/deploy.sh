#!/usr/bin/env bash
# Build + deploy the API Gateway/Lambda stack.
#
# `.samignore` is NOT read by `sam build` (verified against SAM CLI 1.163.0 /
# aws-lambda-builders 1.65.0 — neither package references "samignore"; it
# only ever applied to the legacy raw-zip `sam package` flow). CodeUri is the
# repo root (so the Lambdas can import the sibling `mining`/`bedrock`
# packages unchanged), so `sam build`'s CopySource step copies the entire
# repo verbatim — including the gitignored 130MB+ of `data/raw` source
# files and test directories. That alone pushes each function past
# Lambda's 250MB unzipped limit. This script prunes those paths from the
# build output before deploying, since there's no supported exclude
# mechanism for the standard Python/pip build.
set -euo pipefail
cd "$(dirname "$0")"

sam build --template-file template.yaml

for fn in RecommendationFunction AskFunction; do
  rm -rf \
    ".aws-sam/build/$fn/data/raw" \
    ".aws-sam/build/$fn/api/tests" \
    ".aws-sam/build/$fn/mining/tests" \
    ".aws-sam/build/$fn/frontend" \
    ".aws-sam/build/$fn/contextv67" \
    ".aws-sam/build/$fn/.pytest_cache" \
    ".aws-sam/build/$fn/.claude" \
    ".aws-sam/build/$fn/.kiro" \
    ".aws-sam/build/$fn/.git"
done

sam deploy "$@"
