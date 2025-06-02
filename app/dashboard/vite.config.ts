import react from "@vitejs/plugin-react";
import { defineConfig, splitVendorChunkPlugin, type Plugin } from "vite"; // Make sure to import 'Plugin' type
import svgr from "vite-plugin-svgr";
import { visualizer } from "rollup-plugin-visualizer";
import tsconfigPaths from "vite-tsconfig-paths";
import { loadEnv } from 'vite';
import type { ConfigEnv } from 'vite';

// Define the custom plugin to fix the admin root serving in dev mode
function devServerAdminRootFix(): Plugin {
  return {
    name: 'dev-server-admin-root-fix',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        // If the request is for the bare '/admin/' path,
        // rewrite it to '/admin/admin.html' to serve the correct entry file.
        if (req.url === '/admin/') {
          req.url = '/admin/admin.html';
        }
        next();
      });
    }
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }: ConfigEnv) => {
  const env = loadEnv(mode, process.cwd(), '');
  const isDev = mode === 'development' || mode === 'admin' || mode === 'portal';

  const isAdminBuild = mode === 'admin';
  const base = isAdminBuild ? '/admin/' : '/';
  const outDir = isAdminBuild ? 'dist_admin' : 'dist_portal';

  const apiBaseUrl = isDev
    ? `http://${env.VITE_API_TARGET_HOST || 'marzban-panel'}:${env.UVICORN_PORT || 8000}`
    : '';
  const proxyTarget = apiBaseUrl || 'http://marzban-panel:8000';
  const apiBasePath = env.VITE_BASE_API || '/api';

  // Initialize plugins array
  const pluginsToUse: Plugin[] = [
    tsconfigPaths(),
    react({
      include: "**/*.tsx",
    }),
    svgr(),
    visualizer(),
    splitVendorChunkPlugin(),
  ];

  // Conditionally add the dev server fix plugin only for admin mode
  if (isAdminBuild) {
    pluginsToUse.push(devServerAdminRootFix());
  }

  return {
    plugins: pluginsToUse, // Use the constructed plugins array
    base: base,
    build: {
      outDir: outDir,
      assetsDir: 'statics',
      minify: !isDev,
      sourcemap: isDev,
      rollupOptions: {
        input: isAdminBuild ? {
          main: 'admin.html',
          admin: 'src/admin.tsx'
        } : {
          main: 'index.html',
          portal: 'src/main.portal.tsx'
        },
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