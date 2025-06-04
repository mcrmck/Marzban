import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const customConfig = defineConfig({
  theme: {
    tokens: {
      fonts: {
        body: { value: `Inter,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Oxygen,Ubuntu,Cantarell,Fira Sans,Droid Sans,Helvetica Neue,sans-serif` },
      },
      colors: {
        "light-border": { value: "#d2d2d4" },
        primary: {
          50: { value: "#9cb7f2" },
          100: { value: "#88a9ef" },
          200: { value: "#749aec" },
          300: { value: "#618ce9" },
          400: { value: "#4d7de7" },
          500: { value: "#396fe4" },
          600: { value: "#3364cd" },
          700: { value: "#2e59b6" },
          800: { value: "#284ea0" },
          900: { value: "#224389" },
        },
        gray: {
          750: { value: "#222C3B" },
        },
      },
      radii: {
        sm: { value: "6px" },
        md: { value: "8px" },
      },
    },
    semanticTokens: {
      shadows: {
        outline: { value: "0 0 0 2px var(--chakra-colors-primary-200)" },
      },
      colors: {
        "chakra-body-text": {
          default: { value: "gray.800" },
          _dark: { value: "white" },
        },
        "chakra-body-bg": {
          default: { value: "gray.50" },
          _dark: { value: "gray.900" },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, customConfig);
