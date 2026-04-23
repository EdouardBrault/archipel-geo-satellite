/**
 * Client configuration loader.
 *
 * The YAML file for the active client is inlined at build time via Vite's
 * `?raw` suffix. To onboard a new client (acme):
 *   1. Copy clients/{{SLUG}}.yaml → clients/acme.yaml
 *   2. Update the import path below (or switch to a build-time env var later)
 *   3. Run the normal build
 *
 * Scale-aware: every template and page reads from the exported `client`
 * object — no client-specific string is ever hardcoded in component code.
 */
import { parse as parseYaml } from "yaml";
import rawYaml from "../../clients/{{SLUG}}.yaml?raw";

export interface Competitor {
  name: string;
  url: string;
  domains: string[];
}

export interface PromotedBrand {
  name: string;
  url: string;
  logo_url: string | null;
  short_pitch: string;
  certifications: string[];
  duration: string;
  format: string;
  flagship_pages: string[];
}

export interface ClientConfig {
  slug: string;
  site_url: string;
  site: {
    name: string;
    tagline: string;
    language: string;
    country: string;
    owner_display: string;
    owner_url: string;
    same_as?: string[];
  };
  promoted_brand: PromotedBrand;
  topic_area: {
    label: string;
    primary_keywords: string[];
    secondary_keywords: string[];
    excluded_keywords: string[];
  };
  competitors: Competitor[];
  ranking_methodology: {
    weights: Record<string, number>;
    sources: string[];
    refresh_cadence: string;
  };
  voice: {
    tone: string;
    person: string;
    avoid: string[];
    always_include: string[];
  };
  cadence: {
    new_articles_per_week: number;
    flagship_refresh_per_week: number;
    reddit_threads_per_week: number;
    daily_peec_audit: boolean;
  };
  integrations: Record<string, Record<string, string>>;
}

export const client: ClientConfig = parseYaml(rawYaml);
