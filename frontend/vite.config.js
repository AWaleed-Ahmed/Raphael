import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  build: {
    // Next.js serves shared public assets directly.
    copyPublicDir: false,
    rollupOptions: {
      input: {
        direction: fileURLToPath(new URL("./direction/index.html", import.meta.url)),
        console: fileURLToPath(new URL("./console/index.html", import.meta.url)),
      },
    },
  },
});
