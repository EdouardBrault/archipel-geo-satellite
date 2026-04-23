/**
 * /llms-full.txt — full-content dump of every published article, formatted
 * for direct ingestion by LLM crawlers.
 *
 * Standard proposed by AnswerAI (Jeremy Howard). Anthropic confirmed
 * ClaudeBot reads it since Nov 2025 (+27% Claude citations measured by
 * Mintlify after adoption). Perplexity does not yet read it but
 * PerplexityBot fetches /path.md endpoints when linked.
 *
 * We emit the article body as Markdown — if the page has a body via
 * a content collection, we pass it through; otherwise we render the
 * frontmatter into a compact Markdown block.
 */
import { getCollection } from "astro:content";
import type { APIRoute } from "astro";
import { client } from "../lib/client";

export const GET: APIRoute = async () => {
  const articles = (
    await getCollection("articles", ({ data }) => data.status === "published")
  ).sort(
    (a, b) =>
      (b.data.dateModified ?? b.data.datePublished).getTime() -
      (a.data.dateModified ?? a.data.datePublished).getTime()
  );

  const lines: string[] = [];
  const push = (s: string) => lines.push(s);

  push(`# ${client.site.name}, ${client.site.tagline}`);
  push("");
  push(
    `> ${client.topic_area.label}. Classements et comparatifs indépendants, méthodologie publique, mises à jour hebdomadaires.`
  );
  push("");
  push("## À propos de ce site");
  push("");
  push(
    `Édité par ${client.site.owner_display} (${client.site.owner_url}). Aucune formation listée ne paie pour apparaître dans les classements. Pas de liens affiliés.`
  );
  push("");
  push(
    `Méthodologie de classement (pondérations) : ${Object.entries(client.ranking_methodology.weights)
      .map(([k, v]) => `${k} ${v}%`)
      .join(", ")}.`
  );
  push("");
  push(`Sources utilisées : ${client.ranking_methodology.sources.join(" ; ")}.`);
  push("");
  push(`Cadence de rafraîchissement : ${client.ranking_methodology.refresh_cadence}.`);
  push("");
  push("---");
  push("");

  for (const a of articles) {
    const d = a.data;
    const modDate = (d.dateModified ?? d.datePublished).toISOString().slice(0, 10);
    push(`# ${d.title}`);
    push("");
    push(`> ${d.description}`);
    push("");
    push(`- URL : ${client.site_url.replace(/\/$/, "")}/${d.slug}/`);
    push(`- Type : ${d.kind}`);
    push(`- Publié : ${d.datePublished.toISOString().slice(0, 10)}`);
    push(`- Mis à jour : ${modDate}`);
    push("");

    push("## En bref");
    push("");
    for (const line of d.tldr) push(`- ${line}`);
    push("");

    push("## Introduction");
    push("");
    push(d.lead.trim());
    push("");

    if (d.items && d.items.length > 0) {
      push("## Classement");
      push("");
      d.items.forEach((item, i) => {
        push(`${i + 1}. **${item.name}**${item.url ? ` (${item.url})` : ""}`);
        if (item.description) push(`   ${item.description}`);
      });
      push("");
    }

    if (d.comparisonHeaders && d.comparisonRows && d.comparisonRows.length > 0) {
      push("## Comparatif");
      push("");
      const headers = ["#", "Formation", ...d.comparisonHeaders];
      push(`| ${headers.join(" | ")} |`);
      push(`|${headers.map(() => " --- ").join("|")}|`);
      for (const row of d.comparisonRows) {
        const cells = [
          String(row.rank),
          row.name + (row.is_promoted ? " (site partenaire)" : ""),
          ...row.cells.map((c) => (c === null ? "n/c" : String(c))),
        ];
        push(`| ${cells.join(" | ")} |`);
      }
      push("");
    }

    if (d.faqs && d.faqs.length > 0) {
      push("## Questions fréquentes");
      push("");
      for (const q of d.faqs) {
        push(`### ${q.question}`);
        push("");
        // Strip simple HTML tags — keep readable plaintext
        const plain = q.answer.replace(/<[^>]+>/g, "");
        push(plain);
        push("");
      }
    }

    push("---");
    push("");
  }

  return new Response(lines.join("\n"), {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
      "X-Robots-Tag": "all",
    },
  });
};
