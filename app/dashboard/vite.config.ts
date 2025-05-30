import react from "@vitejs/plugin-react";
import { defineConfig, splitVendorChunkPlugin } from "vite";
import svgr from "vite-plugin-svgr";
import { visualizer } from "rollup-plugin-visualizer";
import tsconfigPaths from "vite-tsconfig-paths";


// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    tsconfigPaths(),
    react({
      include: "**/*.tsx",
    }),
    svgr(),
    visualizer(),
    splitVendorChunkPlugin(),
  ],
  build: {
    minify: false, // Disable minification completely to preserve console logs
    sourcemap: true, // Enable source maps for better debugging
    rollupOptions: {
      output: {
        manualChunks: undefined
      }
    }
  }
});
