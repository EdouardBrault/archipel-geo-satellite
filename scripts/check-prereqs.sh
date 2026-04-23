#!/usr/bin/env bash
# Verify that every binary + auth needed by bootstrap.sh is in place.
# Exits non-zero on the first missing item, with a clear remediation hint.

set -euo pipefail

fail() {
  echo "::ERROR:: $*" >&2
  exit 1
}

# --- binaries ---------------------------------------------------------

command -v gh        >/dev/null || fail "gh CLI missing. Install from https://cli.github.com, then 'gh auth login'."
command -v wrangler  >/dev/null || command -v npx >/dev/null || fail "wrangler (or npx) missing. 'npm i -g wrangler' or install node."
command -v python3   >/dev/null || fail "python3 missing."
command -v node      >/dev/null || fail "node missing (>=22)."
command -v npm       >/dev/null || fail "npm missing."
command -v yq        >/dev/null || fail "yq missing. Install from https://github.com/mikefarah/yq, or 'brew install yq'."
command -v jq        >/dev/null || fail "jq missing. 'brew install jq'."
command -v git       >/dev/null || fail "git missing."
command -v curl      >/dev/null || fail "curl missing."
command -v openssl   >/dev/null || fail "openssl missing."

# --- python version ---------------------------------------------------

PY_VER=$(python3 -c 'import sys; print(".".join(str(x) for x in sys.version_info[:2]))')
case "$PY_VER" in
  3.11|3.12|3.13|3.14) : ;;
  *) fail "python3 must be >= 3.11 (found $PY_VER)." ;;
esac

# --- auth -------------------------------------------------------------

gh auth status >/dev/null 2>&1 || fail "gh not authenticated. Run 'gh auth login'."

# wrangler auth is checked lazily: wrangler whoami exits non-zero if not logged in.
WRANGLER="wrangler"
command -v wrangler >/dev/null || WRANGLER="npx -y wrangler"
$WRANGLER whoami >/dev/null 2>&1 || fail "wrangler not authenticated. Run 'wrangler login'."

# --- required env vars ------------------------------------------------

check_env() {
  local var=$1
  local hint=$2
  if [ -z "${!var:-}" ]; then
    fail "env var \$$var missing. $hint"
  fi
}

check_env ANTHROPIC_API_KEY     "Generate at https://console.anthropic.com/settings/keys"
check_env PEEC_AI_API_KEY       "Get the project-scoped key from the client's Peec AI account."
check_env SLACK_WEBHOOK_URL     "Create the webhook manually (see docs/SLACK_WEBHOOK.md)."
check_env CLOUDFLARE_ACCOUNT_ID "Get it from wrangler whoami, or dash.cloudflare.com sidebar."
check_env CLOUDFLARE_API_TOKEN  "Create with 'Cloudflare Pages: Edit' permission at /profile/api-tokens."
# Optional but recommended:
# WIKIDATA_BOT_USER, WIKIDATA_BOT_PASS (only if create_entity is true)
# BING_API_KEY (increases submissions above IndexNow)
# IONOS_API_KEY (automates DNS for rank-ly.com)

echo "All prerequisites OK."
