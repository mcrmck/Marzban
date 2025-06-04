/**
 * Client layout wrapper
 * Provides consistent layout structure for client portal pages
 */

import { Outlet } from "react-router-dom";
import { Box, Flex } from "@chakra-ui/react";
import { ClientHeader } from "../../../components/client/ClientHeader";
import { ProtectedRoute } from "../../../shared/components/ProtectedRoute";

const ClientLayout = () => {
  return (
    <ProtectedRoute requiredRole="client">
      <Flex direction="column" minHeight="100vh">
        <ClientHeader />
        <Box flex="1" p={6}>
          <Outlet />
        </Box>
      </Flex>
    </ProtectedRoute>
  );
};

export default ClientLayout;