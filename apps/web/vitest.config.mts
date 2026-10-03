import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@researchly/contract": path.resolve(import.meta.dirname, "../../packages/contract/src/index.ts"),
      "client-only": path.resolve(import.meta.dirname, "tests/unit/stubs/empty.ts"),
      "@": path.resolve(import.meta.dirname, "."),
    },
  },
  test: {
    include: ["tests/unit/**/*.test.ts"],
    environment: "node",
  },
});
