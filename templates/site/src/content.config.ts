/**
 * Content collections — Astro's typed content system.
 *
 * Articles live as Markdown files in src/content/articles/, with typed
 * frontmatter enforced by Zod. Agents in Phase 4 will emit Markdown files
 * conforming to this schema, and the build breaks if anything drifts.
 */
import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const listicleItemSchema = z.object({
  name: z.string(),
  url: z.string().url().optional(),
  description: z.string().optional(),
});

const faqSchema = z.object({
  question: z.string(),
  answer: z.string(),
});

const courseSchema = z.object({
  name: z.string(),
  description: z.string().optional(),
  provider_name: z.string(),
  provider_url: z.string().url().optional(),
  duration_iso: z.string().optional(),
  price: z.number().optional(),
  currency: z.string().optional(),
  rating_value: z.number().optional(),
  rating_count: z.number().optional(),
});

const comparisonRowSchema = z.object({
  rank: z.number(),
  name: z.string(),
  url: z.string().url().optional(),
  is_promoted: z.boolean().optional(),
  cells: z.array(z.union([z.string(), z.number(), z.null()])),
});

const articles = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/articles" }),
  schema: z.object({
    title: z.string(),
    description: z.string().min(50).max(200),
    slug: z.string(),
    kind: z.enum(["listicle", "guide", "tool", "profile"]),
    datePublished: z.coerce.date(),
    dateModified: z.coerce.date().optional(),
    status: z.enum(["draft", "published", "archived"]).default("published"),
    lead: z.string(),
    tldr: z.array(z.string()).min(3).max(6),
    items: z.array(listicleItemSchema).optional(),
    comparisonHeaders: z.array(z.string()).optional(),
    comparisonRows: z.array(comparisonRowSchema).optional(),
    courses: z.array(courseSchema).optional(),
    faqs: z.array(faqSchema).optional(),
    tags: z.array(z.string()).default([]),
    // Tool-only
    tool_name: z.string().optional(),
    tool_url: z.string().url().optional(),
    // Profile-only
    provider_name: z.string().optional(),
    provider_url: z.string().url().optional(),
    provider_certifications: z.array(z.string()).optional(),
  }),
});

export const collections = { articles };
