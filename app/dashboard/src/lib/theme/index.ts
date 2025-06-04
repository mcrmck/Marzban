/**
 * Theme configuration exports
 * Consolidated theme utilities and configurations
 */

import { createSystem, defaultConfig } from "@chakra-ui/react";

// Base theme configuration
const baseTheme = createSystem(defaultConfig, {
  theme: {
    tokens: {
      colors: {
        gray: {
          50: { value: "#fafafa" },
          100: { value: "#f5f5f5" },
          200: { value: "#eeeeee" },
          300: { value: "#d9d9d9" },
          400: { value: "#bfbfbf" },
          500: { value: "#8c8c8c" },
          600: { value: "#595959" },
          700: { value: "#434343" },
          800: { value: "#262626" },
          900: { value: "#1f1f1f" },
        },
        brand: {
          50: { value: "#f0f9ff" },
          100: { value: "#e0f2fe" },
          200: { value: "#bae6fd" },
          300: { value: "#7dd3fc" },
          400: { value: "#38bdf8" },
          500: { value: "#0ea5e9" },
          600: { value: "#0284c7" },
          700: { value: "#0369a1" },
          800: { value: "#075985" },
          900: { value: "#0c4a6e" },
        },
        success: {
          50: { value: "#f6ffed" },
          500: { value: "#52c41a" },
          600: { value: "#389e0d" },
        },
        error: {
          50: { value: "#fff2f0" },
          500: { value: "#ff4d4f" },
          600: { value: "#cf1322" },
        },
        warning: {
          50: { value: "#fffbe6" },
          500: { value: "#faad14" },
          600: { value: "#d48806" },
        },
      },
      fonts: {
        heading: { value: "Inter, -apple-system, BlinkMacSystemFont, sans-serif" },
        body: { value: "Inter, -apple-system, BlinkMacSystemFont, sans-serif" },
      },
    },
    semanticTokens: {
      colors: {
        "chakra-body-text": {
          default: { value: "{colors.gray.800}" },
          _dark: { value: "white" },
        },
        "chakra-body-bg": {
          default: { value: "white" },
          _dark: { value: "{colors.gray.900}" },
        },
      },
    },
  },
});

// Admin theme (blue accent)
export const adminTheme = createSystem(defaultConfig, {
  ...baseTheme._config,
  theme: {
    ...baseTheme._config.theme,
    semanticTokens: {
      ...baseTheme._config.theme?.semanticTokens,
      colors: {
        ...baseTheme._config.theme?.semanticTokens?.colors,
        "app-accent": {
          default: { value: "{colors.brand.500}" },
          _dark: { value: "{colors.brand.400}" },
        },
      },
    },
  },
});

// Client theme (green accent)
export const clientTheme = createSystem(defaultConfig, {
  ...baseTheme._config,
  theme: {
    ...baseTheme._config.theme,
    tokens: {
      ...baseTheme._config.theme?.tokens,
      colors: {
        ...baseTheme._config.theme?.tokens?.colors,
        brand: {
          50: { value: "#f0fdf9" },
          100: { value: "#dcfcef" },
          200: { value: "#bbf7e0" },
          300: { value: "#86efcc" },
          400: { value: "#4adeb5" },
          500: { value: "#22c55e" },
          600: { value: "#16a34a" },
          700: { value: "#15803d" },
          800: { value: "#166534" },
          900: { value: "#14532d" },
        },
      },
    },
    semanticTokens: {
      ...baseTheme._config.theme?.semanticTokens,
      colors: {
        ...baseTheme._config.theme?.semanticTokens?.colors,
        "app-accent": {
          default: { value: "{colors.brand.500}" },
          _dark: { value: "{colors.brand.400}" },
        },
      },
    },
  },
});

export { baseTheme };
export * from "./colorMode";