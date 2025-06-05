import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    VStack,
    Text,
    Container,
    Heading,
    Code,
    HStack,
    useClipboard,
    IconButton
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../lib/stores";
import { ClipboardIcon } from "@heroicons/react/24/outline";
import { toaster } from "../../components/shared/ui/toaster";

const ClientRegisterPage = () => {
    const navigate = useNavigate();
    const { register, isLoadingAuth, error } = useClientPortalStore();
    const [accountNumber] = useState<string | null>(null);
    const { copy } = useClipboard({ value: accountNumber || "" });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const success = await register();
            if (success) {
                toaster.create({
                    title: "Account Created",
                    description: "Your account has been created successfully.",
                    type: "success",
                    duration: 5000,
                    closable: true,
                });
                navigate("/account", { replace: true });
            }
        } catch (err) {
            toaster.create({
                title: "Registration Failed",
                description: error || "Failed to create account. Please try again.",
                type: "error",
                duration: 5000,
                closable: true,
            });
        }
    };

    const handleCopyAccountNumber = () => {
        copy();
        toaster.create({
            title: "Copied!",
            description: "Account number copied to clipboard",
            type: "success",
            duration: 2000,
            closable: true,
        });
    };

    return (
        <Container maxW="container.sm" py={10}>
            <VStack gap={8} align="stretch">
                <Box textAlign="center">
                    <Heading size="xl" mb={2}>Create Account</Heading>
                    <Text color="gray.600">Register for a new client account</Text>
                </Box>

                <form onSubmit={handleSubmit}>
                    <VStack gap={4}>
                        {accountNumber && (
                            <Box
                                p={4}
                                borderWidth="1px"
                                borderRadius="md"
                                bg="gray.50"
                                width="full"
                            >
                                <Text mb={2} fontWeight="medium">
                                    Your Account Number
                                </Text>
                                <HStack>
                                    <Code p={2} flex="1">
                                        {accountNumber}
                                    </Code>
                                    <IconButton
                                        aria-label="Copy account number"
                                        onClick={handleCopyAccountNumber}
                                        size="sm"
                                        variant="ghost"
                                    >
                                        <ClipboardIcon style={{ width: 20, height: 20 }} />
                                    </IconButton>
                                </HStack>
                            </Box>
                        )}

                        <Button
                            type="submit"
                            colorScheme="brand"
                            size="lg"
                            width="full"
                            loading={isLoadingAuth}
                            loadingText="Creating account..."
                        >
                            Create Account
                        </Button>

                        <Button
                            variant="ghost"
                            onClick={() => navigate("/login")}
                            size="sm"
                        >
                            Already have an account? Login
                        </Button>
                    </VStack>
                </form>
            </VStack>
        </Container>
    );
};

export default ClientRegisterPage;