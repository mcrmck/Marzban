/**
 * Base theme configuration for Chakra UI v3
 * Shared foundation for both admin and client themes
 * Following official Chakra UI v3 theming guidelines
 */

import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

// Jade nature-inspired color palette
const baseColors = {
  // Natural off-white and warm grays inspired by stone and earth
  gray: {
    50: { value: "#fafaf9" },   // Warm off-white
    100: { value: "#f5f5f4" },  // Light stone
    200: { value: "#e7e5e4" },  // Lighter stone
    300: { value: "#d6d3d1" },  // Medium stone
    400: { value: "#a8a29e" },  // Warm gray
    500: { value: "#78716c" },  // Stone gray
    600: { value: "#57534e" },  // Dark stone
    700: { value: "#44403c" },  // Charcoal
    800: { value: "#292524" },  // Dark charcoal
    900: { value: "#1c1917" },  // Near black
  },
  // Sage and forest green palette inspired by jade and nature
  jade: {
    50: { value: "#f0fdf4" },   // Lightest mint
    100: { value: "#dcfce7" },  // Light mint
    200: { value: "#bbf7d0" },  // Soft green
    300: { value: "#86efac" },  // Light jade
    400: { value: "#4ade80" },  // Jade green
    500: { value: "#22c55e" },  // Primary jade
    600: { value: "#16a34a" },  // Deep jade
    700: { value: "#15803d" },  // Forest green
    800: { value: "#166534" },  // Dark forest
    900: { value: "#14532d" },  // Deep forest
    950: { value: "#0f2419" },  // Darkest forest
  },
  // Sage green for secondary elements
  sage: {
    50: { value: "#f6f7f6" },   // Light sage
    100: { value: "#e8eae7" },  // Soft sage
    200: { value: "#d1d5ce" },  // Medium sage
    300: { value: "#b3bab0" },  // Darker sage
    400: { value: "#8b9488" },  // Deep sage
    500: { value: "#6b7066" },  // Primary sage
    600: { value: "#565b52" },  // Dark sage
    700: { value: "#454942" },  // Forest sage
    800: { value: "#363834" },  // Deep sage
    900: { value: "#2a2c28" },  // Darkest sage
    950: { value: "#1c1e1b" },  // Deepest sage
  },
  // Blue-green for accents
  teal: {
    50: { value: "#f0fdfa" },
    100: { value: "#ccfbf1" },
    200: { value: "#99f6e4" },
    300: { value: "#5eead4" },
    400: { value: "#2dd4bf" },
    500: { value: "#14b8a6" },
    600: { value: "#0d9488" },
    700: { value: "#0f766e" },
    800: { value: "#115e59" },
    900: { value: "#134e4a" },
  },
  // Keep existing colors for compatibility
  green: {
    50: { value: "#f0fdf4" },
    100: { value: "#dcfce7" },
    200: { value: "#bbf7d0" },
    300: { value: "#86efac" },
    400: { value: "#4ade80" },
    500: { value: "#22c55e" },
    600: { value: "#16a34a" },
    700: { value: "#15803d" },
    800: { value: "#166534" },
    900: { value: "#14532d" },
  },
  blue: {
    50: { value: "#eff6ff" },
    100: { value: "#dbeafe" },
    200: { value: "#bfdbfe" },
    300: { value: "#93c5fd" },
    400: { value: "#60a5fa" },
    500: { value: "#3b82f6" },
    600: { value: "#2563eb" },
    700: { value: "#1d4ed8" },
    800: { value: "#1e40af" },
    900: { value: "#1e3a8a" },
  },
  red: {
    50: { value: "#fff5f5" },
    100: { value: "#fed7d7" },
    200: { value: "#feb2b2" },
    300: { value: "#fc8181" },
    400: { value: "#f56565" },
    500: { value: "#e53e3e" },
    600: { value: "#c53030" },
    700: { value: "#9b2c2c" },
    800: { value: "#822727" },
    900: { value: "#63171b" },
  },
  yellow: {
    50: { value: "#fffff0" },
    100: { value: "#fefcbf" },
    200: { value: "#faf089" },
    300: { value: "#f6e05e" },
    400: { value: "#ecc94b" },
    500: { value: "#d69e2e" },
    600: { value: "#b7791f" },
    700: { value: "#975a16" },
    800: { value: "#744210" },
    900: { value: "#5F370E" },
  },
};

// Semantic tokens following Chakra UI v3 guidelines
const baseSemanticTokens = {
  colors: {
    // Base Chakra tokens
    "chakra-body-text": {
      value: { base: "{colors.gray.800}", _dark: "{colors.gray.100}" },
    },
    "chakra-body-bg": {
      value: { base: "{colors.gray.50}", _dark: "{colors.gray.900}" },
    },
    "chakra-border-color": {
      value: { base: "{colors.gray.200}", _dark: "{colors.gray.700}" },
    },
    "chakra-placeholder-color": {
      value: { base: "{colors.gray.400}", _dark: "{colors.gray.500}" },
    },
    
    // Jade semantic color system following guidelines
    "jade.solid": {
      value: { base: "{colors.jade.500}", _dark: "{colors.jade.400}" },
    },
    "jade.contrast": {
      value: { base: "white", _dark: "{colors.gray.900}" },
    },
    "jade.fg": {
      value: { base: "{colors.jade.600}", _dark: "{colors.jade.300}" },
    },
    "jade.muted": {
      value: { base: "{colors.jade.400}", _dark: "{colors.jade.500}" },
    },
    "jade.subtle": {
      value: { base: "{colors.jade.50}", _dark: "{colors.jade.950}" },
    },
    "jade.emphasized": {
      value: { base: "{colors.jade.100}", _dark: "{colors.jade.900}" },
    },
    "jade.focusRing": {
      value: { base: "{colors.jade.500}", _dark: "{colors.jade.400}" },
    },
    
    // Sage semantic colors for secondary elements
    "sage.solid": {
      value: { base: "{colors.sage.500}", _dark: "{colors.sage.400}" },
    },
    "sage.contrast": {
      value: { base: "white", _dark: "{colors.gray.900}" },
    },
    "sage.fg": {
      value: { base: "{colors.sage.600}", _dark: "{colors.sage.300}" },
    },
    "sage.muted": {
      value: { base: "{colors.sage.400}", _dark: "{colors.sage.500}" },
    },
    "sage.subtle": {
      value: { base: "{colors.sage.50}", _dark: "{colors.sage.950}" },
    },
    "sage.emphasized": {
      value: { base: "{colors.sage.100}", _dark: "{colors.sage.900}" },
    },
    
    // Generic surface colors
    "bg.canvas": {
      value: { base: "{colors.gray.50}", _dark: "{colors.gray.900}" },
    },
    "bg.surface": {
      value: { base: "white", _dark: "{colors.gray.800}" },
    },
    "bg.subtle": {
      value: { base: "{colors.gray.100}", _dark: "{colors.gray.800}" },
    },
    "border.default": {
      value: { base: "{colors.gray.200}", _dark: "{colors.gray.700}" },
    },
    "border.emphasized": {
      value: { base: "{colors.gray.300}", _dark: "{colors.gray.600}" },
    },
  },
  shadows: {
    xs: { value: "0 0 0 1px rgba(0, 0, 0, 0.05)" },
    sm: { value: "0 1px 2px 0 rgba(0, 0, 0, 0.05)" },
    base: { value: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)" },
    md: { value: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" },
    lg: { value: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)" },
    xl: { value: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)" },
  },
};

// Base typography
const baseTypography = {
  fonts: {
    heading: { value: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" },
    body: { value: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" },
    mono: { value: "'JetBrains Mono', 'SF Mono', 'Monaco', 'Inconsolata', monospace" },
  },
  fontSizes: {
    xs: { value: "0.75rem" },
    sm: { value: "0.875rem" },
    md: { value: "1rem" },
    lg: { value: "1.125rem" },
    xl: { value: "1.25rem" },
    "2xl": { value: "1.5rem" },
    "3xl": { value: "1.875rem" },
    "4xl": { value: "2.25rem" },
    "5xl": { value: "3rem" },
    "6xl": { value: "3.75rem" },
  },
  fontWeights: {
    hairline: { value: "100" },
    thin: { value: "200" },
    light: { value: "300" },
    normal: { value: "400" },
    medium: { value: "500" },
    semibold: { value: "600" },
    bold: { value: "700" },
    extrabold: { value: "800" },
    black: { value: "900" },
  },
  lineHeights: {
    normal: { value: "normal" },
    none: { value: "1" },
    shorter: { value: "1.25" },
    short: { value: "1.375" },
    base: { value: "1.5" },
    tall: { value: "1.625" },
    taller: { value: "2" },
  },
};

// Base spacing
const baseSpacing = {
  px: { value: "1px" },
  0: { value: "0" },
  0.5: { value: "0.125rem" },
  1: { value: "0.25rem" },
  1.5: { value: "0.375rem" },
  2: { value: "0.5rem" },
  2.5: { value: "0.625rem" },
  3: { value: "0.75rem" },
  3.5: { value: "0.875rem" },
  4: { value: "1rem" },
  5: { value: "1.25rem" },
  6: { value: "1.5rem" },
  7: { value: "1.75rem" },
  8: { value: "2rem" },
  9: { value: "2.25rem" },
  10: { value: "2.5rem" },
  12: { value: "3rem" },
  14: { value: "3.5rem" },
  16: { value: "4rem" },
  20: { value: "5rem" },
  24: { value: "6rem" },
  28: { value: "7rem" },
  32: { value: "8rem" },
  36: { value: "9rem" },
  40: { value: "10rem" },
  44: { value: "11rem" },
  48: { value: "12rem" },
  52: { value: "13rem" },
  56: { value: "14rem" },
  60: { value: "15rem" },
  64: { value: "16rem" },
  72: { value: "18rem" },
  80: { value: "20rem" },
  96: { value: "24rem" },
};

// Component recipes following Chakra UI v3 guidelines
const recipes = {
  // Update component theming to use recipes instead of baseStyle
};

// Base configuration following Chakra UI v3 guidelines
export const baseConfig = defineConfig({
  theme: {
    tokens: {
      colors: baseColors,
      ...baseTypography,
      spacing: baseSpacing,
      radii: {
        none: { value: "0" },
        sm: { value: "0.125rem" },
        base: { value: "0.25rem" },
        md: { value: "0.375rem" },
        lg: { value: "0.5rem" },
        xl: { value: "0.75rem" },
        "2xl": { value: "1rem" },
        "3xl": { value: "1.5rem" },
        full: { value: "9999px" },
      },
    },
    semanticTokens: baseSemanticTokens,
    recipes,
  },
});

// Create base system
export const baseSystem = createSystem(defaultConfig, baseConfig);

export { baseColors, baseSemanticTokens, baseTypography, baseSpacing, recipes };