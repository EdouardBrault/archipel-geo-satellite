/**
 * Append editorial-referral UTM parameters to an outbound URL.
 *
 * We track clicks leaving the satellite site as if they were an affiliate
 * referral — the outbound destination sees `utm_source=<fqdn>` and can
 * attribute traffic. Internal links, anchors, mailto/tel, and already
 * UTM-tagged URLs are returned unchanged.
 *
 * The "slug" + "kind" context is optional: when present, it lets us see
 * which article drove the click in the destination's analytics.
 */
import { client } from "./client";

const SITE_HOST = client.site_url
  .replace(/^https?:\/\//, "")
  .replace(/\/$/, "")
  .toLowerCase();

export function withUtm(
  href: string,
  ctx?: { slug?: string; kind?: string }
): string {
  if (!href) return href;
  if (!/^https?:\/\//i.test(href)) return href; // anchors, mailto, tel, relative
  let url: URL;
  try {
    url = new URL(href);
  } catch {
    return href;
  }
  // Skip internal (same-host) links
  if (url.hostname.toLowerCase().endsWith(SITE_HOST)) return href;
  // Skip already-tagged URLs — don't clobber an existing UTM scheme
  if (url.searchParams.has("utm_source")) return href;

  url.searchParams.set("utm_source", SITE_HOST);
  url.searchParams.set("utm_medium", "referral");
  if (ctx?.slug) {
    url.searchParams.set("utm_campaign", ctx.slug);
  } else {
    url.searchParams.set("utm_campaign", "site");
  }
  if (ctx?.kind) url.searchParams.set("utm_content", ctx.kind);
  return url.toString();
}
