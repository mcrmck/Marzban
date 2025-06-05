import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    Container,
    Heading,
    Text,
    VStack,
    Spinner,
    Alert
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../lib/stores";
import { toaster } from "@/components/ui/toaster";

export const ClientAccountPage = () => {
    const navigate = useNavigate();
    const { clientDetails, fetchClientDetails, isLoadingDetails, logout } = useClientPortalStore();

    useEffect(() => {
        fetchClientDetails().catch(() => {
            toaster.create({
                title: "Error",
                description: "Failed to fetch account details. Please try again.",
                type: "error",
                duration: 5000,
            });
        });
    }, [fetchClientDetails]);

    const handleLogout = async () => {
        try {
            await logout();
            toaster.create({
                title: "Logged Out",
                description: "You have been successfully logged out.",
                type: "success",
                duration: 3000,
                closable: true,
            });
            navigate("/login");
        } catch (error) {
            toaster.create({
                title: "Error",
                description: "Failed to log out. Please try again.",
                type: "error",
                duration: 5000,
                closable: true,
            });
        }
    };

    if (isLoadingDetails) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    return (
        <Container maxW="container.xl" py={10}>
            <VStack gap={8} align="stretch">
                <Box>
                    <Heading size="xl">Account Details</Heading>
                    <Text color="gray.600" mt={2}>
                        View and manage your account information
                    </Text>
                </Box>

                {clientDetails?.user.status === "inactive" && (
                    <Alert.Root status="warning">
                        Your account is currently inactive. Please subscribe to a plan to activate your account.
                    </Alert.Root>
                )}

                <Box
                    p={6}
                    borderWidth="1px"
                    borderRadius="lg"
                    bg="white"
                    shadow="sm"
                >
                    <VStack align="stretch" gap={4}>
                        <Box>
                            <Text fontWeight="medium" color="gray.600">
                                Account Number
                            </Text>
                            <Text fontSize="lg">{clientDetails?.user.account_number}</Text>
                        </Box>

                        <Box>
                            <Text fontWeight="medium" color="gray.600">
                                Status
                            </Text>
                            <Text fontSize="lg" color={clientDetails?.user.status === "active" ? "green.500" : "red.500"}>
                                {clientDetails?.user.status}
                            </Text>
                        </Box>

                        <Box>
                            <Text fontWeight="medium" color="gray.600">
                                Current Plan
                            </Text>
                            <Text fontSize="lg">
                                {clientDetails?.user.plan?.name || "No active plan"}
                            </Text>
                        </Box>

                        <Button
                            colorScheme="red"
                            variant="outline"
                            onClick={handleLogout}
                            alignSelf="flex-start"
                        >
                            Logout
                        </Button>
                    </VStack>
                </Box>
            </VStack>
        </Container>
    );
};