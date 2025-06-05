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
    IconButton,
    useClipboard,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../lib/stores";
import { ClipboardIcon } from "@heroicons/react/24/outline";
import { toaster } from "../../components/shared/ui/toaster";

const ClientRegisterPage = () => {
    const navigate = useNavigate();
    const { register, isLoadingAuth, error } = useClientPortalStore();
    const [accountNumber] = useState<string | null>(null);
    const { copy } = useClipboard({ value: accountNumber || "" });
    // createToast is now imported directly

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
                    <Heading size="xl" mb={2}>Create New Account</Heading>
                    <Text color="gray.600">Register for a new VPN account</Text>
                </Box>

                {accountNumber ? (
                    <Box>
                        <Text mb={4}>Your account has been created! Here's your account number:</Text>
                        <HStack justify="center" mb={4}>
                            <Code p={2} fontSize="lg">{accountNumber}</Code>
                            <IconButton
                                aria-label="Copy account number"
                                onClick={handleCopyAccountNumber}
                            >
                                <ClipboardIcon width={16} height={16} />
                            </IconButton>
                        </HStack>
                        <Text fontSize="sm" color="gray.500" textAlign="center">
                            Please save this number. You'll need it to log in.
                        </Text>
                    </Box>
                ) : (
                    <Button
                        colorScheme="brand"
                        size="lg"
                        onClick={handleSubmit}
                        loading={isLoadingAuth}
                    >
                        Create Account
                    </Button>
                )}
            </VStack>
        </Container>
    );
};

export default ClientRegisterPage;
