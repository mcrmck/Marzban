/**
 * Client theme configuration for Chakra UI v3
 * Green-based color scheme for client portal interface
 */

import { createSystem, defaultConfig } from "@chakra-ui/react";
import { baseColors, baseSemanticTokens, baseTypography, baseSpacing } from "./base";

const clientTheme = createSystem(defaultConfig, {
  theme: {
    tokens: {
      colors: {
        ...baseColors,
        primary: baseColors.green,
      },
      ...baseTypography,
      spacing: baseSpacing,
    },
    semanticTokens: {
      colors: {
        ...baseSemanticTokens.colors,
        // Client-specific semantic colors
        "client-primary": {
          default: { value: "{colors.green.500}" },
          _dark: { value: "{colors.green.400}" },
        },
        "client-primary-hover": {
          default: { value: "{colors.green.600}" },
          _dark: { value: "{colors.green.300}" },
        },
        "client-secondary": {
          default: { value: "{colors.gray.500}" },
          _dark: { value: "{colors.gray.400}" },
        },
        "client-secondary-hover": {
          default: { value: "{colors.gray.600}" },
          _dark: { value: "{colors.gray.300}" },
        },
        // Component-specific colors
        "client-card-bg": {
          default: { value: "white" },
          _dark: { value: "{colors.gray.800}" },
        },
        "client-sidebar-bg": {
          default: { value: "white" },
          _dark: { value: "{colors.gray.900}" },
        },
        "client-sidebar-hover": {
          default: { value: "{colors.gray.100}" },
          _dark: { value: "{colors.gray.700}" },
        },
        "client-sidebar-active": {
          default: { value: "{colors.green.50}" },
          _dark: { value: "{colors.green.900}" },
        },
        // Status colors for VPN states
        "status-connected": {
          default: { value: "{colors.green.500}" },
          _dark: { value: "{colors.green.400}" },
        },
        "status-connecting": {
          default: { value: "{colors.yellow.500}" },
          _dark: { value: "{colors.yellow.400}" },
        },
        "status-disconnected": {
          default: { value: "{colors.red.500}" },
          _dark: { value: "{colors.red.400}" },
        },
      },
      shadows: {
        ...baseSemanticTokens.shadows,
        "client-card": {
          default: { value: "{shadows.base}" },
          _dark: { value: "{shadows.base}" },
        },
        "client-dropdown": {
          default: { value: "{shadows.md}" },
          _dark: { value: "{shadows.md}" },
        },
      },
    },
  },
});

export default clientTheme;