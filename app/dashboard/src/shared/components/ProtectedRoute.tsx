/**
 * Protected route wrapper
 * Handles authentication and role-based access control
 */

import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Box, Spinner, Text } from "@chakra-ui/react";
import { getAdminToken, getClientToken } from "../../lib/utils";

interface ProtectedRouteProps {
  children: ReactNode;
  requiredRole?: "admin" | "client";
  fallbackPath?: string;
}

export const ProtectedRoute = ({
  children,
  requiredRole = "admin",
  fallbackPath
}: ProtectedRouteProps) => {
  const location = useLocation();

  // Determine which auth method to use based on required role
  const token = requiredRole === "admin" ? getAdminToken() : getClientToken();
  const isAuthenticated = !!token;

  // Default fallback paths
  const defaultFallback = requiredRole === "admin" ? "/admin/login" : "/login";
  const redirectTo = fallbackPath || defaultFallback;

  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

// Loading state component for auth checks
export const AuthLoading = () => (
  <Box
    height="100vh"
    display="flex"
    flexDirection="column"
    alignItems="center"
    justifyContent="center"
    gap={4}
  >
    <Spinner size="xl" color="brand.500" />
    <Text color="gray.600">Checking authentication...</Text>
  </Box>
);