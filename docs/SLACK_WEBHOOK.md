# Slack webhook — l'étape UI qui reste manuelle

Slack n'expose pas d'API publique pour créer un webhook. C'est donc la seule étape de bootstrap qui reste UI-only. 30-60 secondes.

## À faire avant de lancer le bootstrap

### 1. Crée le canal

Dans le workspace Archipel, nouveau canal (privé recommandé) :
- Nom : `rank-ly-<slug>` (convention Archipel, pas obligatoire mais facilite le monitoring cross-clients)
- Description : "Notifications agent + digest hebdo pour [Client]"

### 2. Crée l'app Slack (ou réutilise celle d'Archipel)

Si l'app `Archipel Agent` existe déjà :
- Va sur `api.slack.com/apps` → clique dessus → **Incoming Webhooks**
- **Add New Webhook to Workspace** → sélectionne le nouveau canal → **Allow**
- Copie la nouvelle URL webhook (format `https://hooks.slack.com/services/T.../B.../...`)

Si tu crées une nouvelle app (cas rare, par ex pour un workspace client séparé) :
- `api.slack.com/apps` → **Create New App** → **From scratch**
- App Name : `Archipel Agent` · Workspace : celui du canal
- Menu gauche : **Incoming Webhooks** → toggle **Activate** sur ON
- **Add New Webhook to Workspace** → canal → Allow
- Copie l'URL

### 3. Colle la valeur dans ton `.env.onboarding`

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../..."
```

Le bootstrap poste cette valeur comme secret GitHub, tous les agents du client l'utilisent.

## Tester le webhook

Avant de lancer le bootstrap, un ping rapide pour vérifier :

```bash
curl -sS -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test webhook Archipel — si vous voyez ce message, tout est branché."}' \
  "$SLACK_WEBHOOK_URL"
```

Réponse attendue : `ok`. Et le message arrive dans le canal.

## Révocation

Si la valeur fuite ou au départ du collaborateur :
- `api.slack.com/apps` → app → **Incoming Webhooks** → Delete l'ancienne URL
- Regénère un nouveau webhook pour le canal
- Mets à jour le secret GH du client : `gh secret set SLACK_WEBHOOK_URL --body "<new-url>" --repo <owner>/<repo>`

## Pourquoi pas d'API

Slack considère la création de webhooks comme un acte d'administration qui doit passer par le consentement explicite de l'utilisateur (OAuth flow interactif). Les Slack Apps peuvent programmatiquement publier VIA un webhook, mais pas en créer un.

Alternative théorique : utiliser une Bot Token et la Web API (`chat.postMessage`). Ça nécessiterait un OAuth par client, plus complexe. Le webhook est plus simple et largement suffisant pour notre usage.
