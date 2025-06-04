import { useTheme } from "next-themes";

export type ColorMode = "light" | "dark";

// Re-export next-themes hook as useColorMode for compatibility
export const useColorMode = () => {
  const { theme, setTheme } = useTheme();
  
  return {
    colorMode: (theme as ColorMode) || "light",
    setColorMode: (mode: ColorMode) => setTheme(mode),
    toggleColorMode: () => setTheme(theme === "light" ? "dark" : "light"),
  };
};

// Re-export ThemeProvider as ColorModeProvider for compatibility
export { ThemeProvider as ColorModeProvider } from "next-themes";

export function getColor(lightColor: string, darkColor: string, colorMode: ColorMode): string {
  return colorMode === "light" ? lightColor : darkColor;
}

export const colorModeValue = (light: string, dark: string) => ({
  _light: light,
  _dark: dark,
});