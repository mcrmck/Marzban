/**
 * Client application entry point  
 * Contains client portal routing and providers
 */

import { Routes, Route, Navigate } from "react-router-dom";
import { GlobalProviders } from "../../shared/providers/GlobalProviders";

// Client pages - lazy loaded
import { lazy } from "react";

const ClientLandingPage = lazy(() => import("../../app/client/ClientLandingPage"));
const ClientLoginPage = lazy(() => import("../../app/client/ClientLoginPage"));
const ClientRegisterPage = lazy(() => import("../../app/client/ClientRegisterPage"));
const ClientAccountPage = lazy(() => import("../../app/client/ClientAccountPage"));
const ClientPlansPage = lazy(() => import("../../app/client/ClientPlansPage"));
const ClientServersPage = lazy(() => import("../../app/client/ClientServersPage"));
const ClientStripeCancelPage = lazy(() => import("../../app/client/ClientStripeCancelPage"));
const ClientStripeSuccessPage = lazy(() => import("../../app/client/ClientStripeSuccessPage"));

// Client layout
import ClientLayout from "./components/ClientLayout";

// Note: ClientPortalContext is a Zustand store, not a provider

const ClientApp = () => {
  return (
    <GlobalProviders mode="client">
      <Routes>
        <Route path="/" element={<ClientLandingPage />} />
        <Route path="/login" element={<ClientLoginPage />} />
        <Route path="/register" element={<ClientRegisterPage />} />
        
        {/* Protected client routes */}
        <Route path="/*" element={<ClientLayout />}>
          <Route path="account" element={<ClientAccountPage />} />
          <Route path="plans" element={<ClientPlansPage />} />
          <Route path="servers" element={<ClientServersPage />} />
          <Route path="payment/success" element={<ClientStripeSuccessPage />} />
          <Route path="payment/cancel" element={<ClientStripeCancelPage />} />
          <Route path="*" element={<Navigate to="/account" replace />} />
        </Route>
      </Routes>
    </GlobalProviders>
  );
};

export default ClientApp;