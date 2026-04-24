// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { rehypeUtm } from "./src/plugins/rehype-utm.mjs";

const SITE = "https://{{FQDN}}";

// For the sitemap: for every emitted URL, try to read the matching article's
// `dateModified` frontmatter so the lastmod we announce is the real one,
// not the build time. Google/Bing discount sitemaps that bump lastmod on
// every build without a real content change.
function lastmodFromArticle(url) {
  try {
    const u = new URL(url);
    const slug = u.pathname.replace(/^\/|\/$/g, "");
    if (!slug) return undefined;
    const mdPath = join(
      process.cwd(),
      "src",
      "content",
      "articles",
      `${slug}.md`
    );
    if (!existsSync(mdPath)) return undefined;
    const content = readFileSync(mdPath, "utf-8");
    const m =
      content.match(/^dateModified:\s*['"]?(\d{4}-\d{2}-\d{2})/m) ||
      content.match(/^datePublished:\s*['"]?(\d{4}-\d{2}-\d{2})/m);
    if (!m) return undefined;
    return new Date(m[1]).toISOString();
  } catch {
    return undefined;
  }
}

export default defineConfig({
  site: SITE,
  integrations: [
    sitemap({
      changefreq: "weekly",
      priority: 0.7,
      serialize(item) {
        const lastmod = lastmodFromArticle(item.url);
        if (lastmod) item.lastmod = lastmod;
        return item;
      },
    }),
  ],
  markdown: {
    // Rewrites every external <a href> in Markdown bodies with editorial
    // referral UTMs. See src/plugins/rehype-utm.mjs.
    rehypePlugins: [
      [rehypeUtm, { siteHost: "{{FQDN}}" }],
    ],
  },
  build: {
    // Emit every URL as a clean folder with index.html — better for LLM crawlers.
    format: "directory",
  },
});
