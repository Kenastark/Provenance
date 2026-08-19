import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true },
  build: {
    rollupOptions: {
      output: {
        // MapLibre and Recharts are most of the bundle and neither changes often.
        // Splitting them keeps the app chunk small enough to re-download on a
        // deploy without pulling the whole map engine with it.
        manualChunks: {
          maplibre: ["maplibre-gl"],
          charts: ["recharts"],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    alias: {
      // maplibre-gl reaches for URL.createObjectURL and a WebGL context at import
      // time, so importing it under jsdom throws before any test runs. The real
      // engine is exercised by the Playwright e2e in a real browser.
      "maplibre-gl": fileURLToPath(new URL("./src/test/maplibre-stub.ts", import.meta.url)),
    },
    // Playwright owns e2e; vitest must not try to run those specs.
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        // Generated from the backend contract; the drift check is its gate, and
        // covering a literal table would measure nothing.
        "src/api/*.generated.ts",
        "src/api/schema.d.ts",
        // The composition root and the MapLibre GL binding: neither runs under
        // jsdom (no WebGL), and both are exercised by the Playwright e2e instead.
        "src/main.tsx",
        "src/features/map/mapEngine.ts",
        "src/**/*.d.ts",
        "src/**/__tests__/**",
        "src/test/**",
      ],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
});
