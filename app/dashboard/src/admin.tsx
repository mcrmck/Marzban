import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import { ChakraProvider, Spinner, Box } from "@chakra-ui/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import dayjs from "dayjs";
import Duration from "dayjs/plugin/duration";
import LocalizedFormat from "dayjs/plugin/localizedFormat";
import RelativeTime from "dayjs/plugin/relativeTime";
import Timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

// Import i18n setup
import "./locales/i18n";

// Import themes and utilities
import adminTheme from "./theme/adminTheme";
import { queryClient } from "./lib/utils/react-query";
import { updateThemeColor } from "./lib/utils/themeColor";
import { ColorModeProvider } from "./lib/theme/colorMode";
import { adminRouter } from "./app/admin/AdminRouter";
import "./index.scss";

dayjs.extend(Timezone);
dayjs.extend(LocalizedFormat);
dayjs.extend(utc);
dayjs.extend(RelativeTime);
dayjs.extend(Duration);

// Loading component for i18n
const I18nLoading = () => (
  <Box
    height="100vh"
    display="flex"
    alignItems="center"
    justifyContent="center"
  >
    <Spinner size="xl" color="sage.solid" />
  </Box>
);

updateThemeColor("light");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ColorModeProvider 
      attribute="class" 
      defaultTheme="system" 
      enableSystem
      disableTransitionOnChange={false}
    >
      <ChakraProvider value={adminTheme}>
        <QueryClientProvider client={queryClient}>
          <Suspense fallback={<I18nLoading />}>
            <RouterProvider router={adminRouter} />
          </Suspense>
        </QueryClientProvider>
      </ChakraProvider>
    </ColorModeProvider>
  </React.StrictMode>
);