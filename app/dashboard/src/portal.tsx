import { ChakraProvider, ColorModeScript } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider } from "react-query";
import { RouterProvider } from "react-router-dom";
import { portalRouter } from "./pages/PortalRouter";
import { clientTheme } from "./theme/clientTheme";
import React from "react";
import ReactDOM from "react-dom/client";
import dayjs from "dayjs";
import Duration from "dayjs/plugin/duration";
import LocalizedFormat from "dayjs/plugin/localizedFormat";
import RelativeTime from "dayjs/plugin/relativeTime";
import Timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import "locales/i18n";
import "index.scss";
import { ClientAppInitializer } from "./components/client/ClientAppInitializer";

// Initialize dayjs plugins
dayjs.extend(Timezone);
dayjs.extend(LocalizedFormat);
dayjs.extend(utc);
dayjs.extend(RelativeTime);
dayjs.extend(Duration);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: false,
    },
  },
});

export const Portal = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ChakraProvider theme={clientTheme}>
        <ColorModeScript initialColorMode={clientTheme.config.initialColorMode} />
        <ClientAppInitializer />
        <RouterProvider router={portalRouter} />
      </ChakraProvider>
    </QueryClientProvider>
  );
};

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Portal />
  </React.StrictMode>
);