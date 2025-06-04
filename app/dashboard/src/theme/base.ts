/**
 * Base theme configuration for Chakra UI v3
 * Shared foundation for both admin and client themes
 */

import { createSystem, defaultConfig } from "@chakra-ui/react";

// Base color palette - extending Chakra's default colors
const baseColors = {
  gray: {
    50: { value: "#f7fafc" },
    100: { value: "#edf2f7" },
    200: { value: "#e2e8f0" },
    300: { value: "#cbd5e0" },
    400: { value: "#a0aec0" },
    500: { value: "#718096" },
    600: { value: "#4a5568" },
    700: { value: "#2d3748" },
    800: { value: "#1a202c" },
    900: { value: "#171923" },
  },
  blue: {
    50: { value: "#ebf8ff" },
    100: { value: "#bee3f8" },
    200: { value: "#90cdf4" },
    300: { value: "#63b3ed" },
    400: { value: "#4299e1" },
    500: { value: "#3182ce" },
    600: { value: "#2b6cb0" },
    700: { value: "#2c5282" },
    800: { value: "#2a4365" },
    900: { value: "#1a365d" },
  },
  green: {
    50: { value: "#f0fff4" },
    100: { value: "#c6f6d5" },
    200: { value: "#9ae6b4" },
    300: { value: "#68d391" },
    400: { value: "#48bb78" },
    500: { value: "#38a169" },
    600: { value: "#2f855a" },
    700: { value: "#276749" },
    800: { value: "#22543d" },
    900: { value: "#1c4532" },
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

// Component-specific theme tokens
const components = {
  Button: {
    baseStyle: {
      fontWeight: "semibold",
      borderRadius: "md",
    },
    variants: {
      solid: {
        bg: "primary.500",
        color: "white",
        _hover: {
          bg: "primary.600",
        },
      },
      outline: {
        borderColor: "primary.500",
        color: "primary.500",
        _hover: {
          bg: "primary.50",
        },
      },
      ghost: {
        color: "primary.500",
        _hover: {
          bg: "primary.50",
        },
      },
    },
    sizes: {
      sm: {
        px: 3,
        py: 1,
        fontSize: "sm",
      },
      md: {
        px: 4,
        py: 2,
        fontSize: "md",
      },
      lg: {
        px: 6,
        py: 3,
        fontSize: "lg",
      },
    },
  },
  Card: {
    baseStyle: {
      p: 6,
      bg: "white",
      borderRadius: "lg",
      boxShadow: "base",
    },
  },
  Input: {
    baseStyle: {
      field: {
        bg: "white",
        borderRadius: "md",
        _hover: {
          borderColor: "primary.500",
        },
        _focus: {
          borderColor: "primary.500",
          boxShadow: "0 0 0 1px var(--chakra-colors-primary-500)",
        },
      },
    },
  },
  Select: {
    baseStyle: {
      field: {
        bg: "white",
        borderRadius: "md",
        _hover: {
          borderColor: "primary.500",
        },
        _focus: {
          borderColor: "primary.500",
          boxShadow: "0 0 0 1px var(--chakra-colors-primary-500)",
        },
      },
    },
  },
  Table: {
    baseStyle: {
      th: {
        fontWeight: "semibold",
        textTransform: "none",
        letterSpacing: "normal",
      },
      td: {
        py: 4,
      },
    },
  },
};

// Create base system
export const baseSystem = createSystem(defaultConfig, {
  config: {
    initialColorMode: "system",
    useSystemColorMode: true,
  },
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
    components,
  },
});

export { baseColors, baseSemanticTokens, baseTypography, baseSpacing, components };