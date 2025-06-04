/**
 * Base theme configuration for Chakra UI v3
 * Shared foundation for both admin and client themes
 */

import { createSystem, defaultConfig } from "@chakra-ui/react";

// Base color palette
const baseColors = {
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
  success: {
    50: { value: "#f6ffed" },
    100: { value: "#d9f7be" },
    200: { value: "#b7eb8f" },
    300: { value: "#95de64" },
    400: { value: "#73d13d" },
    500: { value: "#52c41a" },
    600: { value: "#389e0d" },
    700: { value: "#237804" },
    800: { value: "#135200" },
    900: { value: "#092b00" },
  },
  error: {
    50: { value: "#fff2f0" },
    100: { value: "#ffccc7" },
    200: { value: "#ffa39e" },
    300: { value: "#ff7875" },
    400: { value: "#ff4d4f" },
    500: { value: "#f5222d" },
    600: { value: "#cf1322" },
    700: { value: "#a8071a" },
    800: { value: "#820014" },
    900: { value: "#5c0011" },
  },
  warning: {
    50: { value: "#fffbe6" },
    100: { value: "#fff1b8" },
    200: { value: "#ffe58f" },
    300: { value: "#ffd666" },
    400: { value: "#ffc53d" },
    500: { value: "#faad14" },
    600: { value: "#d48806" },
    700: { value: "#ad6800" },
    800: { value: "#874d00" },
    900: { value: "#613400" },
  },
  info: {
    50: { value: "#e6f7ff" },
    100: { value: "#bae7ff" },
    200: { value: "#91d5ff" },
    300: { value: "#69c0ff" },
    400: { value: "#40a9ff" },
    500: { value: "#1890ff" },
    600: { value: "#096dd9" },
    700: { value: "#0050b3" },
    800: { value: "#003a8c" },
    900: { value: "#002766" },
  },
};

// Base semantic tokens
const baseSemanticTokens = {
  colors: {
    "chakra-body-text": {
      default: { value: "{colors.gray.800}" },
      _dark: { value: "white" },
    },
    "chakra-body-bg": {
      default: { value: "white" },
      _dark: { value: "{colors.gray.900}" },
    },
    "chakra-border-color": {
      default: { value: "{colors.gray.200}" },
      _dark: { value: "{colors.gray.700}" },
    },
    "chakra-placeholder-color": {
      default: { value: "{colors.gray.400}" },
      _dark: { value: "{colors.gray.500}" },
    },
    // Card backgrounds
    "card-bg": {
      default: { value: "white" },
      _dark: { value: "{colors.gray.800}" },
    },
    // Sidebar/navigation
    "sidebar-bg": {
      default: { value: "white" },
      _dark: { value: "{colors.gray.900}" },
    },
    // Input backgrounds
    "input-bg": {
      default: { value: "white" },
      _dark: { value: "{colors.gray.800}" },
    },
    // Table backgrounds
    "table-stripe": {
      default: { value: "{colors.gray.50}" },
      _dark: { value: "{colors.gray.800}" },
    },
  },
  shadows: {
    "card-shadow": {
      default: { value: "0 1px 3px 0 rgba(0, 0, 0, 0.1)" },
      _dark: { value: "0 1px 3px 0 rgba(0, 0, 0, 0.3)" },
    },
    "dropdown-shadow": {
      default: { value: "0 4px 6px -1px rgba(0, 0, 0, 0.1)" },
      _dark: { value: "0 4px 6px -1px rgba(0, 0, 0, 0.3)" },
    },
  },
};

// Base fonts
const baseFonts = {
  heading: { value: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" },
  body: { value: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" },
  mono: { value: "'JetBrains Mono', 'SF Mono', 'Monaco', 'Inconsolata', monospace" },
};

// Base spacing
const baseSpacing = {
  xs: { value: "0.5rem" },
  sm: { value: "0.75rem" },
  md: { value: "1rem" },
  lg: { value: "1.5rem" },
  xl: { value: "2rem" },
  "2xl": { value: "3rem" },
  "3xl": { value: "4rem" },
};

// Create base system
export const baseSystem = createSystem(defaultConfig, {
  theme: {
    tokens: {
      colors: baseColors,
      fonts: baseFonts,
      spacing: baseSpacing,
      radii: {
        sm: { value: "0.25rem" },
        md: { value: "0.375rem" },
        lg: { value: "0.5rem" },
        xl: { value: "0.75rem" },
        "2xl": { value: "1rem" },
        full: { value: "9999px" },
      },
    },
    semanticTokens: baseSemanticTokens,
  },
});

export { baseColors, baseSemanticTokens, baseFonts, baseSpacing };