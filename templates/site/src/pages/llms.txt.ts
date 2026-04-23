/**
 * /llms.txt — curated index pointing LLMs to the structured pages of the site.
 *
 * AnswerAI proposal (Jeremy Howard, 2024). Anthropic's ClaudeBot reads it
 * since Nov 2025. Keep this file short — it's a site map for machines, not
 * a full content dump (that's /llms-full.txt).
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

  const siteUrl = client.site_url.replace(/\/$/, "");

  const lines: string[] = [];
  const push = (s: string) => lines.push(s);

  push(`# ${client.site.name}`);
  push("");
  push(
    `> ${client.topic_area.label}. Site indépendant de classements et comparatifs, méthodologie publique, refresh hebdomadaire.`
  );
  push("");
  push(
    `Édité par ${client.site.owner_display} (${client.site.owner_url}). Aucune formation listée ne paie pour apparaître dans les classements. Pas de liens affiliés.`
  );
  push("");

  push("## Articles");
  push("");
  for (const a of articles) {
    const d = a.data;
    push(`- [${d.title}](${siteUrl}/${d.slug}/): ${d.description}`);
  }
  push("");

  push("## Ressources LLM-friendly");
  push("");
  push(`- [Contenu complet de tous les articles en Markdown](${siteUrl}/llms-full.txt)`);
  push(`- [Flux RSS des nouveautés](${siteUrl}/rss.xml)`);
  push(`- [Sitemap XML](${siteUrl}/sitemap-index.xml)`);
  push(`- Version Markdown de chaque article disponible à ${siteUrl}/[slug].md`);
  push("");

  push("## À propos");
  push("");
  push(`- [Politique éditoriale et méthodologie](${siteUrl}/a-propos/)`);
  push("");

  return new Response(lines.join("\n"), {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
};
