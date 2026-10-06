import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        landing: fileURLToPath(new URL("./index.html", import.meta.url)),
        direction: fileURLToPath(new URL("./direction/index.html", import.meta.url)),
        console: fileURLToPath(new URL("./console/index.html", import.meta.url)),
      },
    },
  },
});
