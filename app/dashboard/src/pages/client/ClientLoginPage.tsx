import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
    Box,
    Button,
    Input,
    VStack,
    Text,
    Container,
    Heading,
    Field,
} from "@chakra-ui/react";
import { useClientPortalStore, useIsAuthenticated, useIsLoadingAuth, useAuthError, useLogin } from "../../lib/stores";
import { toaster } from "@/components/ui/toaster";

interface LocationState {
    from?: {
        pathname: string;
    };
}

export const ClientLoginPage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const login = useLogin();
    const isLoadingAuth = useIsLoadingAuth();
    const error = useAuthError();
    const isAuthenticated = useIsAuthenticated();
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
            toaster.create({
                title: "Login Failed",
                description: error || "Please check your account number and try again.",
                type: "error",
                duration: 5000,
                closable: true,
            });
        }
    };

    return (
        <Container maxW="container.sm" py={10}>
            <VStack gap={8} align="stretch">
                <Box textAlign="center">
                    <Heading size="xl" mb={2}>Client Portal Login</Heading>
                    <Text color="gray.600">Enter your account number to access your portal</Text>
                </Box>

                <form onSubmit={handleSubmit}>
                    <VStack gap={4}>
                        <Field.Root>
                            <Field.Label>Account Number</Field.Label>
                            <Input
                                type="text"
                                value={accountNumber}
                                onChange={(e) => setAccountNumber(e.target.value)}
                                placeholder="Enter your account number"
                                size="lg"
                            />
                            {error && <Field.ErrorText>{error}</Field.ErrorText>}
                        </Field.Root>

                        <Button
                            type="submit"
                            colorScheme="brand"
                            size="lg"
                            width="full"
                            loading={isLoadingAuth}
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