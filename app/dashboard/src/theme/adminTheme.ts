/**
 * Admin theme configuration for Chakra UI v3
 * Blue-based color scheme for administrative interface
 */

import { createSystem, defaultConfig } from "@chakra-ui/react";
import { baseColors, baseSemanticTokens, baseTypography, baseSpacing } from "./base";

const adminTheme = createSystem(defaultConfig, {
  theme: {
    tokens: {
      colors: {
        ...baseColors,
        primary: baseColors.blue,
      },
      ...baseTypography,
      spacing: baseSpacing,
    },
    semanticTokens: {
      colors: {
        ...baseSemanticTokens.colors,
        // Admin-specific semantic colors
        "admin-primary": {
          default: { value: "{colors.blue.500}" },
          _dark: { value: "{colors.blue.400}" },
        },
        "admin-primary-hover": {
          default: { value: "{colors.blue.600}" },
          _dark: { value: "{colors.blue.300}" },
        },
        "admin-secondary": {
          default: { value: "{colors.gray.500}" },
          _dark: { value: "{colors.gray.400}" },
        },
        "admin-secondary-hover": {
          default: { value: "{colors.gray.600}" },
          _dark: { value: "{colors.gray.300}" },
        },
        // Component-specific colors
        "admin-card-bg": {
          default: { value: "white" },
          _dark: { value: "{colors.gray.800}" },
        },
        "admin-sidebar-bg": {
          default: { value: "white" },
          _dark: { value: "{colors.gray.900}" },
        },
        "admin-sidebar-hover": {
          default: { value: "{colors.gray.100}" },
          _dark: { value: "{colors.gray.700}" },
        },
        "admin-sidebar-active": {
          default: { value: "{colors.blue.50}" },
          _dark: { value: "{colors.blue.900}" },
        },
      },
      shadows: {
        ...baseSemanticTokens.shadows,
        "admin-card": {
          default: { value: "{shadows.base}" },
          _dark: { value: "{shadows.base}" },
        },
        "admin-dropdown": {
          default: { value: "{shadows.md}" },
          _dark: { value: "{shadows.md}" },
        },
      },
    },
  },
});

export default adminTheme;