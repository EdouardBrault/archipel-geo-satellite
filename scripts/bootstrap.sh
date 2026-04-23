#!/usr/bin/env bash
# archipel-geo-satellite — end-to-end client bootstrap.
#
# Usage:
#   ./scripts/bootstrap.sh path/to/client.yaml
#
# Environment (required):
#   ANTHROPIC_API_KEY        — Claude API key (agency-level, reused)
#   PEEC_AI_API_KEY          — client's Peec AI project-scoped key
#   SLACK_WEBHOOK_URL        — webhook for the client's Slack channel
#   CLOUDFLARE_ACCOUNT_ID    — Archipel's CF account
#   CLOUDFLARE_API_TOKEN     — CF token with Pages:Edit
#
# Environment (optional):
#   BING_API_KEY             — enables the Bing URL Submission API
#   IONOS_API_KEY            — automates DNS if the parent domain is at IONOS
#   WIKIDATA_BOT_USER        — e.g. "Archipel-editorial@archipel-agent"
#   WIKIDATA_BOT_PASS        — bot password
#   PROJECT_PARENT_DIR       — where to create the new project folder (default: ~/archipel-clients)

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_YAML="${1:-}"

if [ -z "$CLIENT_YAML" ] || [ ! -f "$CLIENT_YAML" ]; then
  echo "Usage: $0 path/to/client.yaml" >&2
  exit 2
fi

PROJECT_PARENT_DIR="${PROJECT_PARENT_DIR:-$HOME/archipel-clients}"
mkdir -p "$PROJECT_PARENT_DIR"

SLUG=$(yq -r .slug "$CLIENT_YAML")
GH_OWNER=$(yq -r .integrations.github.owner "$CLIENT_YAML")
GH_REPO=$(yq -r .integrations.github.repo "$CLIENT_YAML")
CF_PROJECT=$(yq -r .integrations.cloudflare.pages_project "$CLIENT_YAML")
DOMAIN_MODE=$(yq -r .domain.mode "$CLIENT_YAML")
if [ "$DOMAIN_MODE" = "subdomain_rankly" ]; then
  SUBDOMAIN=$(yq -r .domain.subdomain "$CLIENT_YAML")
  PARENT_DOMAIN=$(yq -r .domain.parent "$CLIENT_YAML")
  FQDN="${SUBDOMAIN}.${PARENT_DOMAIN}"
else
  FQDN=$(yq -r .domain.standalone_fqdn "$CLIENT_YAML")
fi

OUT_DIR="$PROJECT_PARENT_DIR/$GH_REPO"

echo
echo "=== archipel-geo-satellite bootstrap ==="
echo "  slug       : $SLUG"
echo "  repo       : $GH_OWNER/$GH_REPO"
echo "  fqdn       : $FQDN"
echo "  cf project : $CF_PROJECT"
echo "  output dir : $OUT_DIR"
echo

# ---------- 0. Prerequisites -----------------------------------------

echo "[0/10] Checking prerequisites..."
bash "$SKILL_DIR/scripts/check-prereqs.sh"

# ---------- 1. Instantiate templates ---------------------------------

echo "[1/10] Instantiating templates into $OUT_DIR..."
python3 "$SKILL_DIR/scripts/instantiate.py" "$CLIENT_YAML" --out "$OUT_DIR" --force

# ---------- 2. Init git + create GitHub repo -------------------------

echo "[2/10] Initialising git and creating private GitHub repo..."
cd "$OUT_DIR"
git init -q -b main
git add .
git -c user.name="Archipel Bootstrap" -c user.email="contact@archipelmarketing.com" \
    commit -q -m "Initial scaffold from archipel-geo-satellite skill"

# Create the repo (private) and push. Idempotent: if it already exists, we just add the remote.
if gh repo view "$GH_OWNER/$GH_REPO" >/dev/null 2>&1; then
  echo "  (repo already exists, linking)"
  git remote add origin "https://github.com/$GH_OWNER/$GH_REPO.git" 2>/dev/null || true
else
  gh repo create "$GH_OWNER/$GH_REPO" --private --source=. --push --remote=origin -d "Citation-magnet satellite for client $SLUG"
fi
git push -u origin main

# ---------- 3. Create Cloudflare Pages project -----------------------

echo "[3/10] Creating Cloudflare Pages project..."
WRANGLER="wrangler"
command -v wrangler >/dev/null || WRANGLER="npx -y wrangler"
$WRANGLER pages project create "$CF_PROJECT" --production-branch main || echo "  (project may already exist, continuing)"

# Initial deploy (build first)
echo "[4/10] Building and deploying site for the first time..."
pushd 03-site >/dev/null
npm ci
npm run build
$WRANGLER pages deploy dist --project-name="$CF_PROJECT" --branch=main --commit-dirty true
popd >/dev/null

# ---------- 5. Add custom domain to CF project -----------------------

echo "[5/10] Attaching custom domain $FQDN to the Cloudflare Pages project..."
curl -sS -X POST \
  "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/pages/projects/${CF_PROJECT}/domains" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${FQDN}\"}" | jq '.success, .errors' || true

# ---------- 6. Post GitHub secrets + variables -----------------------

echo "[6/10] Posting GitHub secrets..."
INDEXNOW_KEY=$(ls 03-site/public/*.txt 2>/dev/null | grep -vE 'robots\.txt|INDEXNOW_KEY_PLACEHOLDER' | head -1 | xargs -I {} basename {} .txt)
gh secret set ANTHROPIC_API_KEY     --body "$ANTHROPIC_API_KEY"     --repo "$GH_OWNER/$GH_REPO"
gh secret set PEEC_AI_API_KEY       --body "$PEEC_AI_API_KEY"       --repo "$GH_OWNER/$GH_REPO"
gh secret set SLACK_WEBHOOK_URL     --body "$SLACK_WEBHOOK_URL"     --repo "$GH_OWNER/$GH_REPO"
gh secret set CLOUDFLARE_ACCOUNT_ID --body "$CLOUDFLARE_ACCOUNT_ID" --repo "$GH_OWNER/$GH_REPO"
gh secret set CLOUDFLARE_API_TOKEN  --body "$CLOUDFLARE_API_TOKEN"  --repo "$GH_OWNER/$GH_REPO"
gh secret set INDEXNOW_KEY          --body "$INDEXNOW_KEY"          --repo "$GH_OWNER/$GH_REPO"
[ -n "${BING_API_KEY:-}" ] && gh secret set BING_API_KEY --body "$BING_API_KEY" --repo "$GH_OWNER/$GH_REPO"

gh variable set AGENTS_ENABLED  --body "true" --repo "$GH_OWNER/$GH_REPO"
gh variable set WAYBACK_ENABLED --body "true" --repo "$GH_OWNER/$GH_REPO"

# ---------- 7. Wikidata entity ---------------------------------------

CREATE_WIKIDATA=$(yq -r .integrations.wikidata.create_entity "$CLIENT_YAML")
if [ "$CREATE_WIKIDATA" = "true" ] && [ -n "${WIKIDATA_BOT_USER:-}" ] && [ -n "${WIKIDATA_BOT_PASS:-}" ]; then
  echo "[7/10] Creating Wikidata entity..."
  QID=$(python3 "$SKILL_DIR/scripts/wikidata.py" "03-site/clients/$SLUG.yaml" || echo "")
  if [ -n "$QID" ]; then
    echo "  entity: https://www.wikidata.org/wiki/$QID"
    # Re-commit the updated client yaml with same_as
    git -c user.name="Archipel Bootstrap" -c user.email="contact@archipelmarketing.com" \
        commit -q -am "Add Wikidata sameAs ($QID)" || true
    git push origin main
  fi
else
  echo "[7/10] Wikidata creation skipped (bot creds absent or create_entity=false)."
fi

# ---------- 8. DNS ---------------------------------------------------

echo "[8/10] DNS configuration"
if [ "$DOMAIN_MODE" = "subdomain_rankly" ] && [ -n "${IONOS_API_KEY:-}" ]; then
  echo "  attempting IONOS CNAME $SUBDOMAIN.$PARENT_DOMAIN -> $CF_PROJECT.pages.dev"
  # IONOS Zone API: find zone, POST record
  ZONE_ID=$(curl -sS -H "X-API-Key: $IONOS_API_KEY" \
    "https://api.hosting.ionos.com/dns/v1/zones" | jq -r ".[] | select(.name==\"$PARENT_DOMAIN\") | .id")
  if [ -n "$ZONE_ID" ]; then
    curl -sS -X PATCH \
      -H "X-API-Key: $IONOS_API_KEY" \
      -H "Content-Type: application/json" \
      "https://api.hosting.ionos.com/dns/v1/zones/$ZONE_ID" \
      -d "[{\"name\":\"$SUBDOMAIN.$PARENT_DOMAIN\",\"type\":\"CNAME\",\"content\":\"$CF_PROJECT.pages.dev\",\"ttl\":3600}]" \
      >/dev/null
    echo "  CNAME posted via IONOS API."
  else
    echo "  :warning: zone $PARENT_DOMAIN not found in IONOS account, skipping."
  fi
else
  echo
  echo "  Add the following DNS record at your registrar:"
  echo "    Type:   CNAME"
  echo "    Host:   ${SUBDOMAIN:-<yourhost>}"
  echo "    Target: $CF_PROJECT.pages.dev"
  echo "    TTL:    3600"
  echo
fi

# ---------- 9. Trigger first write-and-publish -----------------------

echo "[9/10] Triggering the first article via write-and-publish workflow..."
gh workflow run write-and-publish.yml --repo "$GH_OWNER/$GH_REPO" --ref main >/dev/null || true
echo "  (check https://github.com/$GH_OWNER/$GH_REPO/actions)"

# ---------- 10. Summary ----------------------------------------------

echo
echo "[10/10] Bootstrap complete."
echo
echo "  Repo       : https://github.com/$GH_OWNER/$GH_REPO"
echo "  CF Pages   : https://dash.cloudflare.com/?to=/:account/workers-and-pages/pages/view/$CF_PROJECT"
echo "  Site (preview) : https://$CF_PROJECT.pages.dev"
echo "  Site (custom)  : https://$FQDN  (active once DNS + SSL propagate, 5-10 min)"
echo
echo "Next manual steps:"
[ "$DOMAIN_MODE" = "subdomain_rankly" ] && [ -z "${IONOS_API_KEY:-}" ] && echo "  • Add the CNAME above in your DNS provider."
[ "$CREATE_WIKIDATA" = "true" ] && [ -z "${WIKIDATA_BOT_USER:-}" ] && echo "  • Wikidata entity not created: generate a bot password and re-run scripts/wikidata.py"
echo "  • Watch Slack (#$(yq -r '.integrations.slack.channel' "$CLIENT_YAML" | sed 's/#//')) for the first article notification."
echo
