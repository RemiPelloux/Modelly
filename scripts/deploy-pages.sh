#!/usr/bin/env bash
# Publish an uploaded Pages artifact and wait until GitHub has finished, however long.
#
#   bash scripts/deploy-pages.sh <artifact-id> <commit>
#
# Runs in the docs workflow after actions/upload-pages-artifact. actions/deploy-pages does
# the same through the same API but cancels the deployment after at most 10 minutes, and
# GitHub sometimes takes longer than that to sync the whole versioned site. This waits up
# to WAIT_MINUTES instead. The build version is <commit>, the docs-site commit this run
# pushed: Pages needs a commit of the repository, and that one is new on every run, so a
# release tag on the same commit as main is still published.
#
# Needs GH_TOKEN, and the job permissions `pages: write` and `id-token: write`.

set -euo pipefail

ARTIFACT_ID="${1:?usage: deploy-pages.sh <artifact-id> <commit>}"
COMMIT="${2:?usage: deploy-pages.sh <artifact-id> <commit>}"
WAIT_MINUTES="${WAIT_MINUTES:-50}"
POLL_SECONDS=20
API="repos/$GITHUB_REPOSITORY/pages/deployments"

oidc_token() {
  curl --silent --fail -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
    "$ACTIONS_ID_TOKEN_REQUEST_URL" | python3 -c 'import json, sys; print(json.load(sys.stdin)["value"])'
}

deployment_id="$(gh api --method POST "$API" \
  -F artifact_id="$ARTIFACT_ID" \
  -f pages_build_version="$COMMIT" \
  -f oidc_token="$(oidc_token)" \
  -q '.status_url | split("/") | last')"
echo "deployment $deployment_id created"

deadline=$((SECONDS + WAIT_MINUTES * 60))
while ((SECONDS < deadline)); do
  status="$(gh api "$API/$deployment_id" -q .status || echo unknown_status)"
  case "$status" in
    succeed) echo "published after ${SECONDS}s"; exit 0 ;;
    deployment_failed | deployment_content_failed | deployment_cancelled | deployment_lost)
      echo "::error::Pages deployment ended with $status"; exit 1 ;;
  esac
  echo "status: $status (${SECONDS}s)"
  sleep "$POLL_SECONDS"
done
echo "::error::Pages deployment still $status after $WAIT_MINUTES minutes"
exit 1
