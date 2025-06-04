/**
 * Client theme configuration for Chakra UI v3
 * Green-based color scheme for client portal interface
 */

import { createSystem, defaultConfig } from "@chakra-ui/react";
import { baseColors, baseSemanticTokens, baseFonts, baseSpacing } from "./base";

const clientTheme = createSystem(defaultConfig, {
  theme: {
    tokens: {
      colors: {
        ...baseColors,
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
        primary: {
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
      fonts: baseFonts,
      spacing: baseSpacing,
    },
    semanticTokens: {
      colors: {
        ...baseSemanticTokens.colors,
        // Client-specific accent colors
        "client-accent": {
          default: { value: "{colors.brand.500}" },
          _dark: { value: "{colors.brand.400}" },
        },
        "client-accent-hover": {
          default: { value: "{colors.brand.600}" },
          _dark: { value: "{colors.brand.300}" },
        },
        // Navigation colors
        "nav-bg": {
          default: { value: "white" },
          _dark: { value: "{colors.gray.800}" },
        },
        "nav-item-hover": {
          default: { value: "{colors.gray.100}" },
          _dark: { value: "{colors.gray.700}" },
        },
        "nav-item-active": {
          default: { value: "{colors.brand.50}" },
          _dark: { value: "{colors.brand.900}" },
        },
        // Status colors for VPN states
        "status-connected": {
          default: { value: "{colors.success.500}" },
          _dark: { value: "{colors.success.400}" },
        },
        "status-connecting": {
          default: { value: "{colors.warning.500}" },
          _dark: { value: "{colors.warning.400}" },
        },
        "status-disconnected": {
          default: { value: "{colors.error.500}" },
          _dark: { value: "{colors.error.400}" },
        },
      },
    },
  },
});

export default clientTheme;