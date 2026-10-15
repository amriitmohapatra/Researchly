import type { Metadata, Viewport } from "next";
import { connection } from "next/server";
import { TOKENS } from "@researchly/design-tokens";
import { ServiceWorker } from "@/components/ServiceWorker";
// The design tokens first (category colours, light and dark: S4d R2), then the page's own styles.
import "../../../packages/design-tokens/dist/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Researchly: a writing coach for research",
  description:
    "Explainable, section-aware feedback on research writing. It advises; it never drafts. Your text is analysed in memory and never stored.",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
  // Installed on iOS (Add to Home Screen): its own window and a short name. The icon is app/apple-icon.png.
  appleWebApp: { capable: true, title: "Researchly", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light dark",
  themeColor: [
    // The page colour, so an installed app's title bar matches the page (design tokens, surface.page).
    { media: "(prefers-color-scheme: light)", color: TOKENS["surface.page"].light },
    { media: "(prefers-color-scheme: dark)", color: TOKENS["surface.page"].dark },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Every route renders per request so proxy.ts can attach a fresh CSP nonce
  // to Next.js's inline bootstrap scripts (a static page would have none).
  await connection();
  return (
    <html lang="en-GB">
      <body>
        {children}
        <ServiceWorker />
      </body>
    </html>
  );
}
