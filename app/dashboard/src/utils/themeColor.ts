import { ColorMode } from "@chakra-ui/react";

export const updateThemeColor = (colorMode: ColorMode) => {
  const el = document.querySelector('meta[name="theme-color"]');
  el?.setAttribute('content', colorMode == "dark" ? "#166534" : "#22c55e");
};
