import React from "react";
import ReactDOM from "react-dom/client";
import { Portal } from "./portal";
import dayjs from "dayjs";
import Duration from "dayjs/plugin/duration";
import LocalizedFormat from "dayjs/plugin/localizedFormat";
import RelativeTime from "dayjs/plugin/relativeTime";
import Timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import "locales/i18n";
import "index.scss";

// Initialize dayjs plugins
dayjs.extend(Timezone);
dayjs.extend(LocalizedFormat);
dayjs.extend(utc);
dayjs.extend(RelativeTime);
dayjs.extend(Duration);

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Portal />
  </React.StrictMode>
);