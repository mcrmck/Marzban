/**
 * Admin layout wrapper
 * Provides consistent layout structure for admin pages
 */

import { Outlet } from "react-router-dom";
import { Box, Flex } from "@chakra-ui/react";
import { Header } from "../../../components/admin/Header";
import { ProtectedRoute } from "../../../shared/components/ProtectedRoute";

const AdminLayout = () => {
  return (
    <ProtectedRoute requiredRole="admin">
      <Flex direction="column" minHeight="100vh">
        <Header />
        <Box flex="1" p={6}>
          <Outlet />
        </Box>
      </Flex>
    </ProtectedRoute>
  );
};

export default AdminLayout;