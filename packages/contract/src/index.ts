/**
 * API contract v1 for Researchly surfaces (web app, Word add-in).
 *
 * Generated types live in ./schema.d.ts (from ../openapi.json, which the
 * engine service exports from its Pydantic models). These aliases are the
 * only hand-written part: names, not shapes.
 */
import type { components } from "./schema";

type S = components["schemas"];

export type AnalyzeRequest = S["AnalyzeRequest"];
export type AnalyzeOptions = S["AnalyzeOptions"];
export type AnalyzeResponse = S["AnalyzeResponse"];
export type Suggestion = S["Suggestion"];
export type Span = S["Span"];
export type Category = S["Category"];
export type Format = S["Format"];
export type FixSafety = S["FixSafety"];
export type Metrics = S["Metrics"];
export type TierHealth = S["TierHealth"];
export type EngineInfo = S["EngineInfo"];
export type HealthResponse = S["HealthResponse"];
export type RuleInfo = S["RuleInfo"];
export type RulesResponse = S["RulesResponse"];
export type ErrorResponse = S["ErrorResponse"];

/** Mirrors schemas.MAX_CONTENT_CHARS; checked client-side for usability only. */
export const MAX_CONTENT_CHARS = 1_000_000;

import readingKey from "../reading-key.json";

/** One reading-key specimen: before + flagged + after is a sentence the engine flags. */
export type Specimen = { before: string; flagged: string; after: string; note: string };

/**
 * The reading key's specimens, one per category. Shared with the engine's test
 * suite (packages/core/tests/test_reading_key.py), which runs each through
 * api.analyze and checks the category, so the key cannot drift from the engine.
 */
export const READING_KEY: Record<Category, Specimen> = {
  correction: readingKey.correction,
  improvement: readingKey.improvement,
  convention: readingKey.convention,
  preference: readingKey.preference,
};
