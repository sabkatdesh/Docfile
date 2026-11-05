import { defineConfig } from "vitest/config";

// The smoke test talks to a real API process. jsdom's origin is set to the Vite dev origin
// because that is the one the API already allows through CORS.
export default defineConfig({
  test: {
    environment: "jsdom",
    environmentOptions: { jsdom: { url: "http://localhost:5173/" } },
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    globalSetup: ["./e2e/globalSetup.ts"],
    include: ["e2e/**/*.test.{ts,tsx}"],
    testTimeout: 60_000,
    css: false,
  },
});
