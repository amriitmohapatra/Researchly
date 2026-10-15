import type { MetadataRoute } from "next";
import { TOKENS } from "@researchly/design-tokens";
import { PWA_ICONS } from "@/lib/pwa";

/**
 * The web app manifest (PLAN S6, "Installable PWA"; P5), served at
 * /manifest.webmanifest and linked from every page by Next.js. It lets a
 * browser install Researchly as an app window: Install from Chrome or
 * Edge's menu, Add to Home Screen on a phone.
 *
 * Colours come from the design tokens: the paper page colour for the title
 * bar and the splash screen. A manifest holds one theme colour; the dark one
 * is set per colour scheme by the theme-color meta tags (app/layout.tsx),
 * which browsers prefer while the app is open.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Researchly",
    short_name: "Researchly",
    description:
      "Explainable, section-aware feedback on research writing. It advises; it never drafts. Your text is analysed in memory and never stored.",
    lang: "en-GB",
    dir: "ltr",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: TOKENS["surface.page"].light,
    theme_color: TOKENS["surface.page"].light,
    categories: ["education", "productivity"],
    icons: [...PWA_ICONS],
  };
}
