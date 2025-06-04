/**
 * Theme color utilities for Chakra UI v3
 * Provides color mode aware color values and theme utilities
 */

import { type ColorMode } from "../theme/colorMode";

/**
 * Get color value based on current color mode
 */
export const getColor = (lightColor: string, darkColor: string, colorMode: ColorMode): string => {
  return colorMode === "light" ? lightColor : darkColor;
};

/**
 * Generate color mode object for Chakra UI
 */
export const colorMode = (light: string, dark: string) => ({
  _light: light,
  _dark: dark,
});

/**
 * Common color constants for the application
 */
export const themeColors = {
  primary: {
    50: "#e6f7ff",
    100: "#bae7ff", 
    500: "#1890ff",
    600: "#096dd9",
    700: "#0050b3",
  },
  gray: {
    50: "#fafafa",
    100: "#f5f5f5",
    200: "#eeeeee",
    300: "#d9d9d9",
    400: "#bfbfbf",
    500: "#8c8c8c",
    600: "#595959",
    700: "#434343",
    800: "#262626",
    900: "#1f1f1f",
  },
  success: {
    50: "#f6ffed",
    500: "#52c41a",
    600: "#389e0d",
  },
  error: {
    50: "#fff2f0", 
    500: "#ff4d4f",
    600: "#cf1322",
  },
  warning: {
    50: "#fffbe6",
    500: "#faad14",
    600: "#d48806",
  },
} as const;

/**
 * Get semantic color values
 */
export const semanticColors = {
  bg: {
    primary: colorMode("white", "gray.900"),
    secondary: colorMode("gray.50", "gray.800"),
    tertiary: colorMode("gray.100", "gray.700"),
  },
  text: {
    primary: colorMode("gray.900", "white"),
    secondary: colorMode("gray.600", "gray.300"),
    muted: colorMode("gray.500", "gray.400"),
  },
  border: {
    default: colorMode("gray.200", "gray.600"),
    hover: colorMode("gray.300", "gray.500"),
  },
} as const;

/**
 * Component color schemes
 */
export const componentColors = {
  card: {
    bg: semanticColors.bg.primary,
    border: semanticColors.border.default,
  },
  input: {
    bg: semanticColors.bg.primary,
    border: semanticColors.border.default,
    focusBorder: themeColors.primary[500],
  },
  button: {
    primary: {
      bg: themeColors.primary[500],
      color: "white",
      _hover: { bg: themeColors.primary[600] },
    },
    secondary: {
      bg: semanticColors.bg.secondary,
      color: semanticColors.text.primary,
      _hover: { bg: semanticColors.bg.tertiary },
    },
  },
} as const;

/**
 * Utility function to create responsive color values
 */
export const responsiveColor = (base: string, lg?: string, md?: string, sm?: string) => ({
  base,
  sm: sm || base,
  md: md || base, 
  lg: lg || base,
});

/**
 * Alpha transparency utilities
 */
export const withAlpha = (color: string, alpha: number): string => {
  return `${color}${Math.round(alpha * 255).toString(16).padStart(2, '0')}`;
};

/**
 * Update theme color for legacy compatibility
 */
export const updateThemeColor = (colorMode: ColorMode) => {
  // Apply color mode to document
  document.documentElement.setAttribute("data-theme", colorMode);
  document.documentElement.style.colorScheme = colorMode;
};

export default {
  getColor,
  colorMode,
  themeColors,
  semanticColors,
  componentColors,
  responsiveColor,
  withAlpha,
  updateThemeColor,
};