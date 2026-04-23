/**
 * /[slug].md — serves a Markdown version of each article, alongside the
 * HTML version. Reduces LLM fetch token cost ~5x vs rendered HTML. Signals
 * to LLM crawlers that the site is machine-friendly.
 *
 * When a LLM requests /my-article.md, we return the raw Markdown body
 * with useful metadata. PerplexityBot is known to fetch these when linked.
 */
import { getCollection } from "astro:content";
import type { APIRoute, GetStaticPaths } from "astro";
import { client } from "../lib/client";

export const getStaticPaths: GetStaticPaths = async () => {
  const articles = await getCollection(
    "articles",
    ({ data }) => data.status === "published"
  );
  return articles.map((a) => ({
    params: { slug: a.data.slug },
    props: { article: a },
  }));
};

export const GET: APIRoute = async ({ props }) => {
  const { article } = props as { article: { data: any; body: string } };
  const d = article.data;
  const modDate = (d.dateModified ?? d.datePublished).toISOString().slice(0, 10);
  const canonical = `${client.site_url.replace(/\/$/, "")}/${d.slug}/`;

  const frontmatter = [
    "---",
    `title: "${d.title.replace(/"/g, '\\"')}"`,
    `description: "${d.description.replace(/"/g, '\\"')}"`,
    `url: ${canonical}`,
    `published: ${d.datePublished.toISOString().slice(0, 10)}`,
    `updated: ${modDate}`,
    `kind: ${d.kind}`,
    `author: ${client.site.owner_display}`,
    `site: ${client.site.name}`,
    "---",
    "",
  ].join("\n");

  const head: string[] = [];
  head.push(`# ${d.title}`);
  head.push("");
  head.push(`*${d.description}*`);
  head.push("");
  head.push(`> Source : ${canonical} · Mis à jour le ${modDate}.`);
  head.push("");

  if (d.tldr?.length) {
    head.push("## En bref");
    head.push("");
    for (const line of d.tldr) head.push(`- ${line}`);
    head.push("");
  }

  head.push(d.lead.trim());
  head.push("");

  if (d.items?.length) {
    head.push("## Classement");
    head.push("");
    d.items.forEach((item: any, i: number) => {
      head.push(`${i + 1}. **${item.name}**${item.url ? ` (${item.url})` : ""}`);
      if (item.description) head.push(`   ${item.description}`);
    });
    head.push("");
  }

  if (d.comparisonHeaders?.length && d.comparisonRows?.length) {
    head.push("## Comparatif");
    head.push("");
    const headers = ["#", "Formation", ...d.comparisonHeaders];
    head.push(`| ${headers.join(" | ")} |`);
    head.push(`|${headers.map(() => " --- ").join("|")}|`);
    for (const row of d.comparisonRows) {
      const cells = [
        String(row.rank),
        row.name + (row.is_promoted ? " ⭐" : ""),
        ...row.cells.map((c: any) => (c === null ? "n/c" : String(c))),
      ];
      head.push(`| ${cells.join(" | ")} |`);
    }
    head.push("");
  }

  // Body (raw Markdown from the article — keep the rich prose)
  const body = (article.body ?? "").trim();

  if (d.faqs?.length) {
    head.push("## Questions fréquentes");
    head.push("");
    for (const q of d.faqs) {
      head.push(`### ${q.question}`);
      head.push("");
      head.push(q.answer.replace(/<[^>]+>/g, ""));
      head.push("");
    }
  }

  const out = frontmatter + head.join("\n") + "\n\n" + body + "\n";

  return new Response(out, {
    status: 200,
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
      "X-Robots-Tag": "all",
    },
  });
};
