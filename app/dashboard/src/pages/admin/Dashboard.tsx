import {
  Box,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  VStack
} from "@chakra-ui/react";
import { CoreSettingsModal } from "../../components/admin/CoreSettingsModal";
import { DeleteUserModal } from "../../components/admin/DeleteUserModal";
import { Filters } from "../../components/admin/Filters";
import { Footer } from "../../components/shared/Footer";
import { Header } from "../../components/admin/Header";
import { NodesUsage } from "../../components/admin/NodesUsage";
import { QRCodeDialog } from "../../components/shared/QRCodeDialog";
import { ResetAllUsageModal } from "../../components/admin/ResetAllUsageModal";
import { ResetUserUsageModal } from "../../components/admin/ResetUserUsageModal";
import { RevokeSubscriptionDialog } from "../../components/admin/RevokeSubscriptionModal";
import { UserDialog } from "../../components/admin/UserDialog";
import { UsersTable } from "../../components/admin/UsersTable";
import { NodesTable } from "../../components/admin/NodesTable";
import { CertificateManagement } from "../../components/admin/CertificateManagement";
import { fetchInbounds, useDashboard } from "../../lib/stores/DashboardContext";
import { FC, useEffect } from "react";
import { Statistics } from "../../components/admin/Statistics";
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

        <Tabs.Root defaultValue="users">
          <TabsList>
            <TabsTrigger value="users">{t("admin.users")}</TabsTrigger>
            <TabsTrigger value="nodes">{t("admin.nodes")}</TabsTrigger>
            <TabsTrigger value="certificates">{t("admin.certificates", "Certificates")}</TabsTrigger>
          </TabsList>

          <TabsContent value="users">
            <Filters />
            <UsersTable />
            <UserDialog />

            {deletingUser && (
              <DeleteUserModal
                open={!!deletingUser}
                onClose={() => onDeletingUser(null)}
                user={deletingUser}
              />
            )}

            <QRCodeDialog />

            {resetUsageUser && (
              <ResetUserUsageModal
                open={!!resetUsageUser}
                onClose={() => onResetUsageUser(null)}
                user={resetUsageUser}
              />
            )}

            {revokeSubscriptionUser && (
              <RevokeSubscriptionDialog
                open={!!revokeSubscriptionUser}
                onClose={() => onRevokeSubscriptionUser(null)}
                user={revokeSubscriptionUser}
              />
            )}
          </TabsContent>

          <TabsContent value="nodes">
            <NodesTable />
          </TabsContent>

          <TabsContent value="certificates">
            <CertificateManagement />
          </TabsContent>
        </Tabs.Root>

        <NodesUsage />
        <ResetAllUsageModal />
        <CoreSettingsModal />
      </Box>
      <Footer />
    </VStack>
  );
};

export default Dashboard;