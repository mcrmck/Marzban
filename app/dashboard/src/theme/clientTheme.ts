/**
 * Client theme configuration for Chakra UI v3
 * Jade green color scheme for client portal interface (Jade VPN)
 */

import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";
import { baseConfig, baseColors, baseSemanticTokens, baseTypography, baseSpacing } from "./base";

// Client-specific configuration extending base
const clientConfig = defineConfig({
  theme: {
    tokens: {
      colors: {
        ...baseColors,
        // Client uses jade as primary for vibrant look
        brand: baseColors.jade,
        accent: baseColors.teal,
      },
      ...baseTypography,
      spacing: baseSpacing,
    },
    semanticTokens: {
      colors: {
        ...baseSemanticTokens.colors,
        
        // Brand color palette (jade) following Chakra guidelines
        "brand.solid": {
          value: { base: "{colors.brand.500}", _dark: "{colors.brand.400}" },
        },
        "brand.contrast": {
          value: { base: "white", _dark: "{colors.gray.900}" },
        },
        "brand.fg": {
          value: { base: "{colors.brand.600}", _dark: "{colors.brand.300}" },
        },
        "brand.muted": {
          value: { base: "{colors.brand.400}", _dark: "{colors.brand.500}" },
        },
        "brand.subtle": {
          value: { base: "{colors.brand.50}", _dark: "{colors.brand.950}" },
        },
        "brand.emphasized": {
          value: { base: "{colors.brand.100}", _dark: "{colors.brand.900}" },
        },
        "brand.focusRing": {
          value: { base: "{colors.brand.500}", _dark: "{colors.brand.400}" },
        },
        
        // Color palette tokens for components
        "colorPalette.solid": {
          value: { base: "{colors.brand.500}", _dark: "{colors.brand.400}" },
        },
        "colorPalette.contrast": {
          value: { base: "white", _dark: "{colors.gray.900}" },
        },
        "colorPalette.fg": {
          value: { base: "{colors.brand.600}", _dark: "{colors.brand.300}" },
        },
        "colorPalette.muted": {
          value: { base: "{colors.brand.400}", _dark: "{colors.brand.500}" },
        },
        "colorPalette.subtle": {
          value: { base: "{colors.brand.50}", _dark: "{colors.brand.950}" },
        },
        "colorPalette.emphasized": {
          value: { base: "{colors.brand.100}", _dark: "{colors.brand.900}" },
        },
        "colorPalette.focusRing": {
          value: { base: "{colors.brand.500}", _dark: "{colors.brand.400}" },
        },
        
        // Override background colors with jade-themed backgrounds
        "bg.canvas": {
          value: { base: "{colors.brand.50}", _dark: "{colors.gray.900}" },
        },
        "bg.surface": {
          value: { base: "white", _dark: "{colors.gray.800}" },
        },
        "bg.subtle": {
          value: { base: "{colors.brand.100}", _dark: "{colors.gray.800}" },
        },
        
        // VPN status semantic colors
        "status.connected": {
          value: { base: "{colors.brand.500}", _dark: "{colors.brand.400}" },
        },
        "status.connecting": {
          value: { base: "{colors.yellow.500}", _dark: "{colors.yellow.400}" },
        },
        "status.disconnected": {
          value: { base: "{colors.red.500}", _dark: "{colors.red.400}" },
        },
        "status.paused": {
          value: { base: "{colors.sage.500}", _dark: "{colors.sage.400}" },
        },
      },
      shadows: baseSemanticTokens.shadows,
    },
  },
});

const clientTheme = createSystem(defaultConfig, clientConfig);

export default clientTheme;