import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  Container,
  Grid,
  Heading,
  Text,
  VStack,
  HStack,
  Badge,
  Spinner,
  Card,
  IconButton,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../lib/stores";
import { QRCodeSVG } from "qrcode.react";
import type { ClientPortalUser, ClientNode } from "../../lib/types";
import { ClipboardIcon } from "@heroicons/react/24/outline";
import { formatBytes, formatDate } from "../../lib/utils";
import { toaster } from "@/components/ui/toaster";

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

const CopyIcon = () => <ClipboardIcon className="w-4 h-4" />;

/* -------------------------------------------------------------------------- */
/* Account content component                                                  */
/* -------------------------------------------------------------------------- */

interface AccountContentProps {
  user: ClientPortalUser;
  active_node?: ClientNode | null;
  available_nodes: ClientNode[];
}

const AccountContent = ({ user, active_node, available_nodes = [] }: AccountContentProps) => {
  const navigate = useNavigate();
  const { logout } = useClientPortalStore();

  const handleLogout = () => {
    logout();
    navigate("/portal/login");
  };

  const handleCopyAccountNumber = async () => {
    try {
      await navigator.clipboard.writeText(user.account_number);
      toaster.create({
        title: "Copied!",
        description: "Account number copied to clipboard",
        type: "success",
        duration: 2000,
      });
    } catch (err) {
      toaster.create({
        title: "Copy failed",
        type: "error",
        duration: 2000,
      });
    }
  };

  return (
    <Container maxW="container.xl" py={10}>
      <VStack gap={8} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <Box>
            <Heading size="xl">Account Dashboard</Heading>
            <Text color="gray.600">Welcome back!</Text>
          </Box>
          <Button colorPalette="red" onClick={handleLogout}>
            Logout
          </Button>
        </HStack>

        {/* Account summary */}
        <Box divideY="1px" divideColor="gray.200" _osDark={{ divideColor: "gray.700" }}>
          {/* Account number & status */}
          <Box py={6}>
            <HStack justify="space-between" align="center" wrap="wrap" gap={4}>
              <VStack align="start" gap={1}>
                <Text fontSize="sm" color="gray.500">
                  Account Number
                </Text>
                <HStack>
                  <Text fontWeight="semibold">{user.account_number}</Text>
                  <IconButton
                    aria-label="Copy account number"
                    size="sm"
                    variant="ghost"
                    onClick={handleCopyAccountNumber}
                  >
                    <CopyIcon />
                  </IconButton>
                </HStack>
              </VStack>
              <Badge colorPalette={user.status === "active" ? "green" : "red"}>{user.status}</Badge>
            </HStack>
          </Box>

          {/* Stats */}
          <Box py={6}>
            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              <Box>
                <Text fontSize="sm" color="gray.500">
                  Data Usage
                </Text>
                <Text fontSize="2xl" fontWeight="bold">
                  {formatBytes((user as any).used_traffic || 0)}
                </Text>
                <Text fontSize="sm" color="gray.500">
                  of {formatBytes(user.data_limit || 0)}
                </Text>
              </Box>
              <Box>
                <Text fontSize="sm" color="gray.500">
                  Expiry Date
                </Text>
                <Text fontSize="2xl" fontWeight="bold">
                  {formatDate(parseInt(user.expire) || 0)}
                </Text>
                <Text fontSize="sm" color="gray.500">
                  {user.expire === "0" ? "Unlimited" : "days remaining"}
                </Text>
              </Box>
              <Box>
                <Text fontSize="sm" color="gray.500">
                  Active Node
                </Text>
                <Text fontSize="2xl" fontWeight="bold">
                  {active_node?.name || "None"}
                </Text>
                <Text fontSize="sm" color="gray.500">
                  {active_node ? "Connected" : "Not connected"}
                </Text>
              </Box>
            </Grid>
          </Box>

          {/* Connection details */}
          {active_node && (
            <Box py={6}>
              <Card.Root>
                <Card.Header>
                  <Heading size="md">Connection Details</Heading>
                </Card.Header>
                <Card.Body>
                  <VStack align="start" gap={4}>
                    <Box>
                      <Text fontSize="sm" color="gray.500">
                        Server Address
                      </Text>
                      <Text>{active_node.address}</Text>
                    </Box>
                    {"port" in active_node && (
                      <Box>
                        <Text fontSize="sm" color="gray.500">
                          Port
                        </Text>
                        <Text>{(active_node as any).port}</Text>
                      </Box>
                    )}
                    {"qr_code" in active_node && (
                      <Box>
                        <Text fontSize="sm" color="gray.500">
                          QR Code
                        </Text>
                        <Box p={2} bg="white" borderRadius="md">
                          <QRCodeSVG value={(active_node as any).qr_code} size={200} />
                        </Box>
                      </Box>
                    )}
                  </VStack>
                </Card.Body>
              </Card.Root>
            </Box>
          )}
        </Box>
      </VStack>
    </Container>
  );
};

/* -------------------------------------------------------------------------- */
/* Page wrapper                                                               */
/* -------------------------------------------------------------------------- */

const ClientAccountPage = () => {
  const {
    clientDetails,
    fetchClientDetails,
    isLoadingDetails,
  } = useClientPortalStore();

  const user = clientDetails?.user;
  const active_node = clientDetails?.active_node;
  const available_nodes = clientDetails?.available_nodes;

  useEffect(() => {
    fetchClientDetails();
  }, [fetchClientDetails]);

  if (isLoadingDetails) {
    return (
      <Container centerContent py={10}>
        <Spinner size="xl" />
      </Container>
    );
  }

  if (!user) return null;

  return (
    <AccountContent
      user={user}
      active_node={active_node}
      available_nodes={available_nodes || []}
    />
  );
};


export default ClientAccountPage;
