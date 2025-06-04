/**
 * Unified application entry point
 * Single entry for both admin and client portals
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { GlobalProviders } from './shared/providers/GlobalProviders';
import { adminRouter } from './app/admin/AdminRouter';
import { portalRouter } from './pages/PortalRouter';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import relativeTime from 'dayjs/plugin/relativeTime';
import './index.scss';

// Initialize dayjs plugins
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);

// Determine app mode from URL or build configuration
const getAppMode = (): "admin" | "client" => {
  const path = window.location.pathname;
  if (path.startsWith("/admin") || path.startsWith("/dashboard")) {
    return "admin";
  }
  return "client";
};

const appMode = getAppMode();
const router = appMode === "admin" ? adminRouter : portalRouter;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <GlobalProviders mode={appMode}>
      <RouterProvider router={router} />
    </GlobalProviders>
  </React.StrictMode>
);