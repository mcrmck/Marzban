import react from "@vitejs/plugin-react";
import { defineConfig, splitVendorChunkPlugin } from "vite";
import svgr from "vite-plugin-svgr";
import { visualizer } from "rollup-plugin-visualizer";
import tsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isDev = mode === 'development';

  return {
    plugins: [
      tsconfigPaths(),
      react({
        include: "**/*.tsx",
      }),
      svgr(),
      visualizer(),
      splitVendorChunkPlugin(),
    ],
    base: '/dashboard/',
    build: {
      outDir: 'build',
      assetsDir: 'statics',
      minify: !isDev, // Only disable minification in development
      sourcemap: isDev, // Only enable source maps in development
      rollupOptions: {
        output: {
          manualChunks: undefined
        }
      }
    },
    server: {
      port: 3000,
      strictPort: true,
      host: '0.0.0.0'
    }
  };
});
