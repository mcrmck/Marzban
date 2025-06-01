import { Box, Tabs, TabList, TabPanels, Tab, TabPanel, VStack } from "@chakra-ui/react";
import { CoreSettingsModal } from "components/CoreSettingsModal";
import { DeleteUserModal } from "components/DeleteUserModal";
import { Filters } from "components/Filters";
import { Footer } from "components/Footer";
import { Header } from "components/Header";
import { NodesUsage } from "components/NodesUsage";
import { QRCodeDialog } from "components/QRCodeDialog";
import { ResetAllUsageModal } from "components/ResetAllUsageModal";
import { ResetUserUsageModal } from "components/ResetUserUsageModal";
import { RevokeSubscriptionModal } from "components/RevokeSubscriptionModal";
import { UserDialog } from "components/UserDialog";
import { UsersTable } from "components/UsersTable";
import { NodesTable } from "components/NodesTable";
import { fetchInbounds, useDashboard } from "contexts/DashboardContext";
import { FC, useEffect } from "react";
import { Statistics } from "../components/Statistics";
import { useTranslation } from "react-i18next";

export const Dashboard: FC = () => {
  const {
    deletingUser,
    onDeletingUser,
    resetUsageUser,
    onResetUsageUser,
    revokeSubscriptionUser,
    onRevokeSubscriptionUser,
    refetchUsers
  } = useDashboard();
  const { t } = useTranslation();

  useEffect(() => {
    refetchUsers();
    fetchInbounds();
  }, [refetchUsers]);

  return (
    <VStack justifyContent="space-between" minH="100vh" p="6" rowGap={4}>
      <Box w="full">
        <Header />
        <Statistics mt="4" />

        <Tabs mt="4">
          <TabList>
            <Tab>{t("users")}</Tab>
            <Tab>{t("nodes")}</Tab>
          </TabList>

          <TabPanels>
            <TabPanel>
              <Filters />
              <UsersTable />
              <UserDialog />

              {deletingUser && (
                <DeleteUserModal
                  isOpen={!!deletingUser}
                  onClose={() => onDeletingUser(null)}
                  user={deletingUser}
                />
              )}

              <QRCodeDialog />

              {resetUsageUser && (
                <ResetUserUsageModal
                  isOpen={!!resetUsageUser}
                  onClose={() => onResetUsageUser(null)}
                  user={resetUsageUser}
                />
              )}

              {revokeSubscriptionUser && (
                <RevokeSubscriptionModal
                  isOpen={!!revokeSubscriptionUser}
                  onClose={() => onRevokeSubscriptionUser(null)}
                  user={revokeSubscriptionUser}
                />
              )}
            </TabPanel>

            <TabPanel>
              <NodesTable />
            </TabPanel>
          </TabPanels>
        </Tabs>

        <NodesUsage />
        <ResetAllUsageModal />
        <CoreSettingsModal />
      </Box>
      <Footer />
    </VStack>
  );
};

export default Dashboard;