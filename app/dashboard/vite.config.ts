/**
 * Unified Vite configuration for both admin and client portals
 * Supports single build with dynamic routing and optimized development experience
 */

import react from "@vitejs/plugin-react";
import { defineConfig, splitVendorChunkPlugin, type Plugin } from "vite";
import svgr from "vite-plugin-svgr";
import { visualizer } from "rollup-plugin-visualizer";
import { loadEnv } from 'vite';
import type { ConfigEnv } from 'vite';

// Custom plugin for dev server routing
function devServerRoutingFix(): Plugin {
  return {
    name: 'dev-server-routing-fix',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url || '';
        
        // Handle admin routes
        if (url.startsWith('/admin') && !url.includes('.') && !url.startsWith('/api')) {
          req.url = '/admin.html';
        }
        // Handle client routes (spa fallback)
        else if (!url.startsWith('/api') && !url.includes('.') && !url.startsWith('/admin')) {
          req.url = '/index.html';
        }
        
        next();
      });
    }
  };
}

export default defineConfig(async ({ mode }: ConfigEnv) => {
  const env = loadEnv(mode, process.cwd(), '');
  const isDev = mode === 'development';
  
  // Determine build target from mode
  const isAdminBuild = mode === 'admin';
  const isClientBuild = mode === 'portal' || mode === 'client';
  const isUnifiedBuild = !isAdminBuild && !isClientBuild; // Default unified build

  // Build configuration
  const getOutDir = () => {
    if (isAdminBuild) return 'dist_admin';
    if (isClientBuild) return 'dist_portal';
    return 'dist'; // Unified build
  };

  const getBase = () => {
    if (isAdminBuild) return '/admin/';
    return '/';
  };

  const apiBaseUrl = isDev
    ? `http://${env.VITE_API_TARGET_HOST || 'marzban-panel'}:${env.UVICORN_PORT || 8000}`
    : '';
  const proxyTarget = apiBaseUrl || 'http://marzban-panel:8000';

  // Dynamic import of ESM-only module
  const { default: tsconfigPaths } = await import('vite-tsconfig-paths');

  // Plugins configuration
  const plugins: Plugin[] = [
    tsconfigPaths({
      projects: ['./tsconfig.json']
    }),
    react({
      include: "**/*.{jsx,tsx}",
    }),
    svgr({
      include: "**/*.svg?react",
    }),
    splitVendorChunkPlugin(),
  ];

  if (isDev) {
    plugins.push(devServerRoutingFix());
  }

  if (!isDev) {
    plugins.push(visualizer({
      filename: 'dist/stats.html',
      open: false
    }));
  }

  // Build options
  const getBuildConfig = () => {
    if (isUnifiedBuild) {
      // Unified build with multiple entry points
      return {
        rollupOptions: {
          input: {
            main: 'index.html',
            admin: 'admin.html'
          },
          output: {
            manualChunks: {
              vendor: ['react', 'react-dom'],
              chakra: ['@chakra-ui/react'],
              router: ['react-router-dom'],
              query: ['@tanstack/react-query'],
            },
            assetFileNames: 'assets/[name].[hash][extname]',
            chunkFileNames: 'assets/[name].[hash].js',
            entryFileNames: 'assets/[name].[hash].js'
          }
        }
      };
    } else {
      // Separate builds
      return {
        rollupOptions: {
          input: isAdminBuild ? 'admin.html' : 'index.html',
          output: {
            assetFileNames: 'statics/[name].[hash][extname]',
            chunkFileNames: 'statics/[name].[hash].js',
            entryFileNames: 'statics/[name].[hash].js'
          }
        }
      };
    }
  };

  return {
    plugins,
    base: getBase(),
    resolve: {
      alias: {
        '@': '/src',
        '@shared': '/src/shared',
        '@admin': '/src/apps/admin',
        '@client': '/src/apps/client',
      }
    },
    build: {
      outDir: getOutDir(),
      assetsDir: isUnifiedBuild ? 'assets' : 'statics',
      minify: !isDev,
      sourcemap: isDev,
      target: 'es2020',
      ...getBuildConfig(),
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
        },
        '/api/portal': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
        },
        '/sub': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
        }
      }
    },
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        '@chakra-ui/react',
        'react-router-dom',
        '@tanstack/react-query',
      ]
    },
    define: {
      __APP_MODE__: JSON.stringify(mode),
      __IS_DEV__: isDev,
    }
  };
});