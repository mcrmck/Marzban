import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
    Box,
    Button,
    FormControl,
    FormLabel,
    Input,
    VStack,
    Text,
    useToast,
    Container,
    Heading,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../store/clientPortalStore";

interface LocationState {
    from?: {
        pathname: string;
    };
}

export const ClientLoginPage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const toast = useToast();
    const { login, isLoadingAuth, error, isAuthenticated } = useClientPortalStore();
    const [accountNumber, setAccountNumber] = useState("");

    useEffect(() => {
        if (isAuthenticated) {
            // Get the location they were trying to go to, or default to account page
            const from = (location.state as LocationState)?.from?.pathname || "/account";
            navigate(from, { replace: true });
        }
    }, [isAuthenticated, navigate, location]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await login(accountNumber);
            // Navigation will be handled by the useEffect above
        } catch (err) {
            toast({
                title: "Login Failed",
                description: error || "Please check your account number and try again.",
                status: "error",
                duration: 5000,
                isClosable: true,
            });
        }
    };

    return (
        <Container maxW="container.sm" py={10}>
            <VStack spacing={8} align="stretch">
                <Box textAlign="center">
                    <Heading size="xl" mb={2}>Client Portal Login</Heading>
                    <Text color="gray.600">Enter your account number to access your portal</Text>
                </Box>

                <form onSubmit={handleSubmit}>
                    <VStack spacing={4}>
                        <FormControl isRequired>
                            <FormLabel>Account Number</FormLabel>
                            <Input
                                type="text"
                                value={accountNumber}
                                onChange={(e) => setAccountNumber(e.target.value)}
                                placeholder="Enter your account number"
                                size="lg"
                            />
                        </FormControl>

                        <Button
                            type="submit"
                            colorScheme="brand"
                            size="lg"
                            width="full"
                            isLoading={isLoadingAuth}
                            loadingText="Logging in..."
                        >
                            Login
                        </Button>

                        <Text fontSize="sm" color="gray.500">
                            Need help? Contact support for assistance.
                        </Text>
                    </VStack>
                </form>
            </VStack>
        </Container>
    );
};