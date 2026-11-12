import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  base: "/haq/",
  plugins: [tsconfigPaths(), react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    cssMinify: false,
    rollupOptions: { input: path.resolve(__dirname, "index.html") },
  },
});
