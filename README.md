# archipel-geo-satellite

Claude Code skill that scaffolds, deploys and operates a **citation-magnet satellite site** for a new Archipel Marketing client. It replicates the stack validated on `formations-nocode.rank-ly.com` (Astro static site, daily agents, GitHub Actions cron, Cloudflare Pages deploy, Wikidata entity, Peec AI integration), instantiated from a single `client.yaml` input.

> **Proprietary / All rights reserved.** This skill is shared publicly for transparency and auditability, not for reuse. See [LICENSE](LICENSE).

## What it does, in one paragraph

Given a filled `client.yaml` and a handful of agency-level credentials in the environment, `scripts/bootstrap.sh` creates a new private GitHub repo, instantiates an Astro site + four agent scripts + six GitHub Actions workflows, posts all required secrets, creates a Cloudflare Pages project, attaches a custom domain, creates a Wikidata entity, and triggers the first automatic article publication. The collaborator still has to (1) paste a CNAME record in the client's DNS, and (2) create a Slack webhook in the client's workspace — both take 30 seconds.

## Install the skill

```bash
# Clone into your local Claude Code skills folder
git clone https://github.com/EdouardBrault/archipel-geo-satellite ~/.claude/skills/archipel-geo-satellite

# Verify Claude sees it
ls ~/.claude/skills/
```

When a collaborator asks Claude "onboard a new Archipel GEO client", Claude picks up this skill from its available-skills list and follows [SKILL.md](SKILL.md).

## Local pre-requisites

- `gh` CLI authenticated (`gh auth status`)
- `wrangler` authenticated (`wrangler whoami`)
- Node ≥ 22, Python ≥ 3.11, `yq`, `jq`
- See [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for the full list

## Invocation

Ask Claude inside any shell where the prerequisites are met:

> "Onboard ACME for an Archipel GEO satellite, config at ./acme-client.yaml"

Claude will:

1. Validate the config
2. Check every prereq via `scripts/check-prereqs.sh`
3. Run `scripts/bootstrap.sh acme-client.yaml`
4. Report status + hand back the DNS record to paste

The bootstrap takes ~5 minutes end-to-end. DNS propagation + SSL add 10-15 minutes before the custom domain is live.

## Directory layout

```
archipel-geo-satellite/
├── SKILL.md                    # Claude's entry point
├── README.md                   # this file
├── LICENSE                     # proprietary
├── client.example.yaml         # copy + fill in
├── templates/
│   ├── site/                   # Astro site template
│   ├── agents/                 # Python agents (draft, fact_check, publish, planner, audit, refresh, replenish, monitor)
│   ├── workflows/              # 5 GitHub Actions workflows (deploy, write-and-publish, weekly-refresh, daily-audit, weekly-ops)
│   └── root/                   # CLAUDE.md, .gitignore, .env.example
├── scripts/
│   ├── bootstrap.sh            # end-to-end orchestrator
│   ├── check-prereqs.sh        # binary + auth + env var check
│   ├── instantiate.py          # template substitution engine
│   └── wikidata.py             # Wikidata entity creation
└── docs/
    ├── GETTING_STARTED.md      # collaborator walkthrough
    ├── METHODOLOGY.md          # 4-phase sprint approach
    ├── EDITORIAL_RULES.md      # no-disclosure, no-em-dash, voice
    ├── INDEXATION_PLAYBOOK.md  # GEO indexation tactics 2026
    ├── DNS_IONOS.md            # IONOS + generic DNS guide
    └── SLACK_WEBHOOK.md        # the 30-second UI step
```

## What happens in the client project after bootstrap

The new repo contains the full stack described in [docs/METHODOLOGY.md](docs/METHODOLOGY.md). The cron schedule is baked in:

- Daily 06:00 UTC: Peec AI snapshot → Slack alerts if shift
- Tuesday + Thursday 07:00 UTC: planner → draft → fact-check → publish
- Monday 07:00 UTC: flagship refresh (top 5 cited articles)
- Sunday 10:00 UTC: queue replenish + weekly digest to Slack

Everything is kill-switched via `gh variable set AGENTS_ENABLED false`.

## Security model

- The skill holds zero credentials. All secrets come from the collaborator's environment at bootstrap time.
- Bootstrap writes secrets directly to GitHub Actions Secrets via `gh secret set` — they are never persisted on disk.
- The generated client repo is **private by default**.
- The skill is MIT-compatible in structure but licensed proprietary: agency tactics and prompts are in the templates and are considered Archipel IP.
