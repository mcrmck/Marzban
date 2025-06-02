import react from "@vitejs/plugin-react";
import { defineConfig, splitVendorChunkPlugin } from "vite";
import svgr from "vite-plugin-svgr";
import { visualizer } from "rollup-plugin-visualizer";
import tsconfigPaths from "vite-tsconfig-paths";
import { loadEnv } from 'vite';
import type { ConfigEnv } from 'vite';

// https://vitejs.dev/config/
export default defineConfig(({ mode }: ConfigEnv) => {
  const env = loadEnv(mode, process.cwd(), '');
  const isDev = mode === 'development';

  // Use mode directly to determine if this is an admin or portal build
  const isAdminBuild = mode === 'admin';
  const base = isAdminBuild ? '/admin/' : '/';
  const outDir = isAdminBuild ? 'dist_admin' : 'dist_portal';

  // Get API base URL from environment or use default
  // In development, use the Docker service name if available, otherwise fallback to localhost
  const apiBaseUrl = isDev
    ? `http://${env.VITE_API_TARGET_HOST || 'marzban-panel'}:${env.UVICORN_PORT || 8000}`
    : '';

  // Ensure apiBaseUrl is always defined for proxy configuration
  const proxyTarget = apiBaseUrl || 'http://marzban-panel:8000';

  // Get API base path from environment
  const apiBasePath = env.VITE_BASE_API || '/api';

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
    base: base,
    build: {
      outDir: outDir,
      assetsDir: 'statics',
      minify: !isDev,
      sourcemap: isDev,
      rollupOptions: {
        input: isAdminBuild ? 'admin.html' : 'index.html',
        output: {
          manualChunks: undefined,
          assetFileNames: 'statics/[name].[hash][extname]',
          chunkFileNames: 'statics/[name].[hash].js',
          entryFileNames: 'statics/[name].[hash].js'
        }
      }
    },
    server: {
      port: isAdminBuild ? 3000 : 3001,
      strictPort: true,
      host: '0.0.0.0',
      proxy: {
        '/api/admin': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          rewrite: (path) => {
            console.log(`[DEBUG] Admin API path: ${path}`);
            return path;
          }
        },
        '/api/portal': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          rewrite: (path) => {
            console.log(`[DEBUG] Portal API path: ${path}`);
            return path;
          }
        },
        '/sub': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          rewrite: (path) => {
            const rewritten = path.replace(/^\/sub/, '');
            console.log(`[DEBUG] Rewriting sub path: ${path} -> ${rewritten}`);
            return rewritten;
          }
        }
      }
    },
    logLevel: 'info',
    hmr: {
      overlay: false
    }
  };
});
