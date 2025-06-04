/**
 * Main application router
 * Handles routing for both admin and client portals based on URL path
 */

import { Routes, Route, Navigate } from "react-router-dom";
import { useEffect, useState } from "react";

// Lazy load applications for better performance
import { lazy, Suspense } from "react";
import { Spinner, Box } from "@chakra-ui/react";

const AdminApp = lazy(() => import("./apps/admin/AdminApp"));
const ClientApp = lazy(() => import("./apps/client/ClientApp"));

// Loading component
const AppLoading = () => (
  <Box
    height="100vh"
    display="flex"
    alignItems="center"
    justifyContent="center"
  >
    <Spinner size="xl" color="brand.500" />
  </Box>
);

export const AppRouter = () => {
  const [currentApp, setCurrentApp] = useState<"admin" | "client">("admin");

  useEffect(() => {
    // Determine app based on URL path
    const path = window.location.pathname;
    if (path.startsWith("/admin") || path === "/dashboard") {
      setCurrentApp("admin");
    } else {
      setCurrentApp("client");
    }
  }, []);

  return (
    <Suspense fallback={<AppLoading />}>
      <Routes>
        {/* Admin routes */}
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="/dashboard/*" element={<AdminApp />} />
        
        {/* Client routes */}
        <Route path="/*" element={<ClientApp />} />
        
        {/* Default redirect */}
        <Route 
          path="/" 
          element={<Navigate to={currentApp === "admin" ? "/admin" : "/portal"} replace />} 
        />
      </Routes>
    </Suspense>
  );
};