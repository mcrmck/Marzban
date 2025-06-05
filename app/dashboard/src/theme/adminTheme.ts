/**
 * Admin theme configuration for Chakra UI v3
 * Sage green color scheme for administrative interface (Jade VPN)
 */

import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";
import { baseConfig, baseColors, baseSemanticTokens, baseTypography, baseSpacing } from "./base";

// Admin-specific configuration extending base
const adminConfig = defineConfig({
  theme: {
    tokens: {
      colors: {
        ...baseColors,
        // Admin uses sage as brand for professional look
        brand: baseColors.sage,
      },
      ...baseTypography,
      spacing: baseSpacing,
    },
    semanticTokens: {
      colors: {
        ...baseSemanticTokens.colors,
        // Admin uses sage as brand color
        "brand.solid": {
          value: { base: "{colors.sage.500}", _dark: "{colors.sage.400}" },
        },
        "brand.contrast": {
          value: { base: "white", _dark: "{colors.gray.900}" },
        },
        "brand.fg": {
          value: { base: "{colors.sage.600}", _dark: "{colors.sage.300}" },
        },
        "brand.muted": {
          value: { base: "{colors.sage.400}", _dark: "{colors.sage.500}" },
        },
        "brand.subtle": {
          value: { base: "{colors.sage.50}", _dark: "{colors.sage.950}" },
        },
        "brand.emphasized": {
          value: { base: "{colors.sage.100}", _dark: "{colors.sage.900}" },
        },
        "brand.focusRing": {
          value: { base: "{colors.sage.500}", _dark: "{colors.sage.400}" },
        },
        
        // Override primary semantic colors for admin
        "colorPalette.solid": {
          value: { base: "{colors.sage.500}", _dark: "{colors.sage.400}" },
        },
        "colorPalette.contrast": {
          value: { base: "white", _dark: "{colors.gray.900}" },
        },
        "colorPalette.fg": {
          value: { base: "{colors.sage.600}", _dark: "{colors.sage.300}" },
        },
        "colorPalette.muted": {
          value: { base: "{colors.sage.400}", _dark: "{colors.sage.500}" },
        },
        "colorPalette.subtle": {
          value: { base: "{colors.sage.50}", _dark: "{colors.sage.950}" },
        },
        "colorPalette.emphasized": {
          value: { base: "{colors.sage.100}", _dark: "{colors.sage.900}" },
        },
        "colorPalette.focusRing": {
          value: { base: "{colors.sage.500}", _dark: "{colors.sage.400}" },
        },
      },
      shadows: baseSemanticTokens.shadows,
    },
  },
});

const adminTheme = createSystem(defaultConfig, adminConfig);

export default adminTheme;