import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    Container,
    Heading,
    Text,
    VStack,
    useToast,
    Spinner,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../store/clientPortalStore";

export const ClientStripeSuccessPage = () => {
    const navigate = useNavigate();
    const toast = useToast();
    const { fetchClientDetails, isLoadingDetails } = useClientPortalStore();

    useEffect(() => {
        fetchClientDetails()
            .then(() => {
                toast({
                    title: "Payment Successful",
                    description: "Your subscription has been activated.",
                    status: "success",
                    duration: 5000,
                    isClosable: true,
                });
            })
            .catch((error) => {
                toast({
                    title: "Error",
                    description: "Failed to update account details. Please try again.",
                    status: "error",
                    duration: 5000,
                    isClosable: true,
                });
            });
    }, [fetchClientDetails, toast]);

    if (isLoadingDetails) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    return (
        <Container maxW="container.sm" py={10}>
            <VStack spacing={8} textAlign="center">
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
                    onClick={() => navigate("/portal/account")}
                >
                    Go to Account
                </Button>
            </VStack>
        </Container>
    );
};