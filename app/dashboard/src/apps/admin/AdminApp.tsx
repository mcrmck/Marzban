/**
 * Admin application entry point
 * Contains admin-specific routing and providers
 */

import { Routes, Route, Navigate } from "react-router-dom";
import { GlobalProviders } from "../../shared/providers/GlobalProviders";

// Admin pages - lazy loaded
import { lazy } from "react";

const Dashboard = lazy(() => import("../../app/admin/Dashboard"));
const Login = lazy(() => import("../../app/shared/Login"));

// Admin layout
import AdminLayout from "./components/AdminLayout";

// Note: These are Zustand stores, not context providers
// The stores are automatically available when imported

const AdminApp = () => {
  return (
    <GlobalProviders mode="admin">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Route>
      </Routes>
    </GlobalProviders>
  );
};

export default AdminApp;