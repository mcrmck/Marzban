import { ChakraProvider } from "@chakra-ui/react";
import dayjs from "dayjs";
import Duration from "dayjs/plugin/duration";
import LocalizedFormat from "dayjs/plugin/localizedFormat";
import RelativeTime from "dayjs/plugin/relativeTime";
import Timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import "locales/i18n";
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "lib/utils/react-query";
import { updateThemeColor } from "lib/utils/themeColor";
import { adminTheme } from "lib/theme";
import { RouterProvider } from "react-router-dom";
import { adminRouter } from "./app/admin/AdminRouter";
import "index.scss";

dayjs.extend(Timezone);
dayjs.extend(LocalizedFormat);
dayjs.extend(utc);
dayjs.extend(RelativeTime);
dayjs.extend(Duration);

updateThemeColor("light");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ChakraProvider value={adminTheme}>
      <QueryClientProvider client={queryClient}>
        <main className="p-8">
          <RouterProvider router={adminRouter} />
        </main>
      </QueryClientProvider>
    </ChakraProvider>
  </React.StrictMode>
);