import { Box, VStack } from "@chakra-ui/react";
import { CoreSettingsModal } from "components/CoreSettingsModal";
import { DeleteUserModal } from "components/DeleteUserModal";
import { Filters } from "components/Filters";
import { Footer } from "components/Footer";
import { Header } from "components/Header";
import { HostsDialog } from "components/HostsDialog";
import { NodesDialog } from "components/NodesModal";
import { NodesUsage } from "components/NodesUsage";
import { QRCodeDialog } from "components/QRCodeDialog";
import { ResetAllUsageModal } from "components/ResetAllUsageModal";
import { ResetUserUsageModal } from "components/ResetUserUsageModal";
import { RevokeSubscriptionModal } from "components/RevokeSubscriptionModal";
import { UserDialog } from "components/UserDialog";
import { UsersTable } from "components/UsersTable";
import { fetchInbounds, useDashboard } from "contexts/DashboardContext";
import { FC, useEffect } from "react";
import { Statistics } from "../components/Statistics";

export const Dashboard: FC = () => {
  // Destructure all necessary state and functions from the context
  const {
    deletingUser,
    onDeletingUser,
    resetUsageUser,
    onResetUsageUser,
    revokeSubscriptionUser,
    onRevokeSubscriptionUser,
    refetchUsers // Keep existing destructured items
  } = useDashboard();

  useEffect(() => {
    // Using refetchUsers from the destructured context
    refetchUsers();
    fetchInbounds();
    // The Zustand `getState()` approach can also work but direct destructuring is common for hooks.
    // useDashboard.getState().refetchUsers();
  }, [refetchUsers]); // Added refetchUsers to dependency array if it's stable, or remove if not needed.

  return (
    <VStack justifyContent="space-between" minH="100vh" p="6" rowGap={4}>
      <Box w="full">
        <Header />
        <Statistics mt="4" />
        <Filters />
        <UsersTable />
        <UserDialog />

        {/* Corrected DeleteUserModal usage */}
        {deletingUser && (
          <DeleteUserModal
            isOpen={!!deletingUser}
            onClose={() => onDeletingUser(null)}
            user={deletingUser}
          />
        )}

        <QRCodeDialog />
        <HostsDialog />

        {/* Corrected ResetUserUsageModal usage */}
        {resetUsageUser && (
          <ResetUserUsageModal
            isOpen={!!resetUsageUser}
            onClose={() => onResetUsageUser(null)}
            user={resetUsageUser}
          />
        )}

        {/* Corrected RevokeSubscriptionModal usage */}
        {revokeSubscriptionUser && (
          <RevokeSubscriptionModal
            isOpen={!!revokeSubscriptionUser}
            onClose={() => onRevokeSubscriptionUser(null)}
            user={revokeSubscriptionUser}
          />
        )}

        <NodesDialog />
        <NodesUsage />
        <ResetAllUsageModal />
        <CoreSettingsModal />
      </Box>
      <Footer />
    </VStack>
  );
};

export default Dashboard;