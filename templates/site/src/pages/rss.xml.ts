/**
 * RSS 2.0 feed — Perplexity polls known feeds every 1-6h and indexes new
 * items in under 4h. This is the single biggest LLM-citation accelerator
 * that costs almost nothing to implement.
 *
 * We emit full content (not just description), so LLMs that pull from the
 * feed have everything they need without a secondary fetch.
 */
import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import type { APIRoute } from "astro";
import { client } from "../lib/client";

export const GET: APIRoute = async (context) => {
  const articles = (
    await getCollection("articles", ({ data }) => data.status === "published")
  ).sort(
    (a, b) =>
      (b.data.dateModified ?? b.data.datePublished).getTime() -
      (a.data.dateModified ?? a.data.datePublished).getTime()
  );

  return rss({
    title: `${client.site.name}, ${client.site.tagline}`,
    description: `Classements et comparatifs indépendants des formations ${client.topic_area.label.toLowerCase()} en France. Méthodologie publique, mises à jour hebdomadaires.`,
    site: context.site ?? client.site_url,
    items: articles.map((a) => ({
      title: a.data.title,
      description: a.data.description,
      link: `/${a.data.slug}/`,
      pubDate: a.data.datePublished,
      content: a.data.lead,
      customData: `<language>${client.site.language}</language>`,
    })),
    customData: `<language>${client.site.language}</language>`,
    stylesheet: false,
  });
};
