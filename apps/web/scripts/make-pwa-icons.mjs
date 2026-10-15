#!/usr/bin/env node
/**
 * The installable app's icons (PLAN S6, "Installable PWA"), drawn from the
 * brand mark in app/icon.svg so there is one source for the mark.
 *
 *   node scripts/make-pwa-icons.mjs
 *
 * Writes, and the PNGs are committed:
 *   public/icons/icon-192.png, icon-512.png    the mark as it is ("any")
 *   public/icons/maskable-192.png, -512.png    full-bleed navy, the letter
 *                                               inside the 80% safe circle
 *   app/apple-icon.png (180)                    full-bleed square; iOS rounds it
 *
 * Uses sharp, which Next.js installs for image optimisation. Run it again
 * only when the mark changes; tests/unit/pwa.test.ts checks the sizes.
 */
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const mark = readFileSync(path.join(root, "app/icon.svg"), "utf8");

const fill = mark.match(/<rect[^>]*fill="([^"]+)"/)?.[1];
const letter = mark.match(/<path[^>]*\/>/)?.[0];
if (!fill || !letter) throw new Error("app/icon.svg: expected one <rect fill> and one <path>");

/** A full-bleed square of the mark's navy with the letter scaled about its centre. */
function square(scale) {
  // The letter's box is centred near (16.5, 16.5) in the 32-unit mark.
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="${fill}"/><g transform="translate(16 16) scale(${scale}) translate(-16.5 -16.5)">${letter}</g></svg>`;
}

async function png(svg, size, out) {
  const file = path.join(root, out);
  mkdirSync(path.dirname(file), { recursive: true });
  await sharp(Buffer.from(svg), { density: Math.ceil((72 * size) / 32) })
    .resize(size, size)
    .png({ compressionLevel: 9 })
    .toFile(file);
  console.log(`wrote ${out} (${size}×${size})`);
}

await png(mark, 192, "public/icons/icon-192.png");
await png(mark, 512, "public/icons/icon-512.png");
// Maskable: the platform may crop to a circle of 80% of the width; 0.72 keeps
// the letter's stroke well inside it.
await png(square(0.72), 192, "public/icons/maskable-192.png");
await png(square(0.72), 512, "public/icons/maskable-512.png");
// Apple touch icon: opaque, no rounded corners of its own.
await png(square(0.82), 180, "app/apple-icon.png");
