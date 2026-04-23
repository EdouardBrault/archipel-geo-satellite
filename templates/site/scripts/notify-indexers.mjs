#!/usr/bin/env node
/**
 * notify-indexers.mjs
 *
 * Post-deploy hook that pushes newly built URLs to:
 *   - IndexNow (Bing, Yandex, DuckDuckGo, Seznam, Naver — one endpoint fans out)
 *   - Bing Webmaster Tools URL Submission API (confirms + WMT dashboard stats)
 *   - Wayback Machine Save Page Now (eventually feeds Common Crawl → Claude/DeepSeek training)
 *   - Slack channel (so we know what went out)
 *
 * The script reads the freshly built sitemap to discover URLs — no need to
 * track state between runs, the sitemap is the source of truth.
 *
 * Environment variables:
 *   INDEXNOW_KEY        — hex key matching the <key>.txt at site root (required)
 *   SITE_URL            — e.g. https://{{FQDN}} (required)
 *   BING_API_KEY        — optional, enables the Bing URL Submission API call
 *   SLACK_WEBHOOK_URL   — optional, enables Slack notification
 *   WAYBACK_ENABLED     — optional, "true" to enable Wayback (slower, runs last)
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

const env = process.env;

function required(name) {
  const v = env[name];
  if (!v) {
    console.error(`[notify-indexers] missing env var: ${name}`);
    process.exit(1);
  }
  return v;
}

const INDEXNOW_KEY = required("INDEXNOW_KEY");
const SITE_URL = required("SITE_URL").replace(/\/$/, "");
const BING_API_KEY = env.BING_API_KEY;
const SLACK_WEBHOOK = env.SLACK_WEBHOOK_URL;
const WAYBACK_ENABLED = env.WAYBACK_ENABLED === "true";

const SITEMAP_PATH = env.SITEMAP_PATH ?? join(process.cwd(), "dist", "sitemap-0.xml");

// ---------- discover URLs ----------

function parseSitemapUrls(xml) {
  // lightweight extractor — no XML parser dep
  const urls = [];
  const re = /<loc>([^<]+)<\/loc>/g;
  let m;
  while ((m = re.exec(xml)) !== null) urls.push(m[1].trim());
  return urls;
}

let urls = [];
try {
  const xml = readFileSync(SITEMAP_PATH, "utf-8");
  urls = parseSitemapUrls(xml);
} catch (e) {
  console.error(`[notify-indexers] cannot read sitemap at ${SITEMAP_PATH}:`, e.message);
  process.exit(1);
}

console.log(`[notify-indexers] discovered ${urls.length} URL(s) from sitemap`);

if (urls.length === 0) {
  console.log("[notify-indexers] nothing to submit — exiting cleanly");
  process.exit(0);
}

// ---------- IndexNow (Bing + partners) ----------

async function submitIndexNow() {
  const host = new URL(SITE_URL).host;
  const body = {
    host,
    key: INDEXNOW_KEY,
    keyLocation: `${SITE_URL}/${INDEXNOW_KEY}.txt`,
    urlList: urls,
  };
  const r = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  console.log(`[notify-indexers] IndexNow: HTTP ${r.status} — ${text || "(empty)"}`);
  return r.ok || r.status === 202; // 202 = Accepted
}

// ---------- Bing Webmaster URL Submission API ----------

async function submitBing() {
  if (!BING_API_KEY) {
    console.log("[notify-indexers] Bing API: skipped (no BING_API_KEY)");
    return null;
  }
  const siteUrl = SITE_URL + "/";
  // Bing batch API caps at 500 URLs per call
  const chunks = [];
  for (let i = 0; i < urls.length; i += 500) chunks.push(urls.slice(i, i + 500));
  let allOk = true;
  for (const chunk of chunks) {
    const body = { siteUrl, urlList: chunk };
    const r = await fetch(
      `https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlBatch?apikey=${BING_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );
    const text = await r.text();
    console.log(`[notify-indexers] Bing: HTTP ${r.status} — ${text.slice(0, 200)}`);
    if (!r.ok) allOk = false;
  }
  return allOk;
}

// ---------- Wayback Machine Save Page Now ----------

async function submitWayback() {
  if (!WAYBACK_ENABLED) {
    console.log("[notify-indexers] Wayback: skipped (WAYBACK_ENABLED != 'true')");
    return null;
  }
  let ok = 0;
  let fail = 0;
  for (const url of urls) {
    try {
      const r = await fetch(`https://web.archive.org/save/${url}`, {
        method: "GET",
        redirect: "follow",
      });
      if (r.ok) ok++;
      else fail++;
      console.log(`[notify-indexers] Wayback ${r.status} — ${url}`);
    } catch (e) {
      fail++;
      console.log(`[notify-indexers] Wayback ERR — ${url}: ${e.message}`);
    }
    // Polite rate limit — SPN is not infinite
    await new Promise((res) => setTimeout(res, 1500));
  }
  console.log(`[notify-indexers] Wayback: ${ok} ok, ${fail} failed`);
  return fail === 0;
}

// ---------- Slack notification ----------

async function notifySlack(results) {
  if (!SLACK_WEBHOOK) return;
  const lines = [
    `:mag: *Indexation push* — ${urls.length} URL(s)`,
    `IndexNow: ${results.indexnow === true ? ":white_check_mark:" : results.indexnow === false ? ":x:" : "—"}`,
    `Bing API: ${results.bing === true ? ":white_check_mark:" : results.bing === false ? ":x:" : results.bing === null ? "_(skipped)_" : "—"}`,
    `Wayback: ${results.wayback === true ? ":white_check_mark:" : results.wayback === false ? ":warning:" : results.wayback === null ? "_(skipped)_" : "—"}`,
  ];
  await fetch(SLACK_WEBHOOK, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: lines.join("\n") }),
  });
}

// ---------- main ----------

(async () => {
  const results = {
    indexnow: await submitIndexNow().catch((e) => {
      console.error("IndexNow error:", e);
      return false;
    }),
    bing: await submitBing().catch((e) => {
      console.error("Bing error:", e);
      return false;
    }),
    wayback: await submitWayback().catch((e) => {
      console.error("Wayback error:", e);
      return false;
    }),
  };
  await notifySlack(results).catch(() => {});
  // Exit 0 even on partial failure — we don't want indexation glitches to
  // block the deploy pipeline. Slack + logs surface anomalies.
  console.log("[notify-indexers] done");
})();
