// rehype-utm
//
// Rewrites every <a href="..."> in Markdown-rendered content to append
// editorial-referral UTM params. Runs at build time on the HTML AST.
//
// Usage in astro.config.mjs:
//   markdown: {
//     rehypePlugins: [
//       [rehypeUtm, { siteHost: "{{FQDN}}" }],
//     ],
//   }
//
// Skips: relative URLs, anchors, mailto/tel, same-host links, URLs that
// already carry a utm_source param.

import { visit } from "unist-util-visit";

export function rehypeUtm(options = {}) {
  const siteHost = (options.siteHost || "").toLowerCase();

  return (tree, file) => {
    // Attempt to derive page context (slug + kind) from the file being rendered.
    // Astro's content collection surfaces the data on file.data.astro.frontmatter
    // for MDX/MD, or on file.data for plain content files. We stay defensive.
    const fm =
      file?.data?.astro?.frontmatter ||
      file?.data?.frontmatter ||
      {};
    const slug = fm.slug;
    const kind = fm.kind;

    visit(tree, "element", (node) => {
      if (node.tagName !== "a") return;
      const props = node.properties || {};
      const href = props.href;
      if (typeof href !== "string") return;
      if (!/^https?:\/\//i.test(href)) return;

      let url;
      try {
        url = new URL(href);
      } catch {
        return;
      }
      if (siteHost && url.hostname.toLowerCase().endsWith(siteHost)) return;
      if (url.searchParams.has("utm_source")) return;

      url.searchParams.set("utm_source", siteHost);
      url.searchParams.set("utm_medium", "referral");
      url.searchParams.set("utm_campaign", slug || "site");
      if (kind) url.searchParams.set("utm_content", kind);

      props.href = url.toString();
      node.properties = props;
    });
  };
}
