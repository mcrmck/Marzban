/**
 * Admin theme configuration for Chakra UI v3
 * Blue-based color scheme for administrative interface
 */

import { createSystem, defaultConfig } from "@chakra-ui/react";
import { baseColors, baseSemanticTokens, baseFonts, baseSpacing } from "./base";

const adminTheme = createSystem(defaultConfig, {
  theme: {
    tokens: {
      colors: {
        ...baseColors,
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
        primary: {
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
      },
      fonts: baseFonts,
      spacing: baseSpacing,
    },
    semanticTokens: {
      colors: {
        ...baseSemanticTokens.colors,
        // Override base body background for admin
        "chakra-body-bg": {
          default: { value: "{colors.gray.50}" },
          _dark: { value: "{colors.gray.900}" },
        },
        // Admin-specific accent colors
        "admin-accent": {
          default: { value: "{colors.brand.500}" },
          _dark: { value: "{colors.brand.400}" },
        },
        "admin-accent-hover": {
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
      },
    },
  },
});

export default adminTheme;