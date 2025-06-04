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
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../lib/stores";
import { toaster } from "@/components/ui/toaster";

const ClientStripeSuccessPage = () => {
    const navigate = useNavigate();
    const { fetchClientDetails, isLoadingDetails } = useClientPortalStore();

    useEffect(() => {
        fetchClientDetails()
            .then(() => {
                toaster.create({
                    title: "Payment Successful",
                    description: "Your subscription has been activated.",
                    type: "success",
                    duration: 5000,
                    closable: true,
                });
            })
            .catch(() => {
                toaster.create({
                    title: "Error",
                    description: "Failed to update account details. Please try again.",
                    type: "error",
                    duration: 5000,
                    closable: true,
                });
            });
    }, [fetchClientDetails]);

    if (isLoadingDetails) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    return (
        <Container maxW="container.sm" py={10}>
            <VStack gap={8} textAlign="center">
                <Box>
                    <Heading size="xl" color="green.500" mb={4}>
                        Payment Successful!
                    </Heading>
                    <Text color="gray.600" fontSize="lg">
                        Thank you for your payment. Your subscription has been activated.
                    </Text>
                </Box>

                <Button
                    colorScheme="blue"
                    size="lg"
                    onClick={() => navigate("/account")}
                >
                    Go to Account
                </Button>
            </VStack>
        </Container>
    );
};

export default ClientStripeSuccessPage;
