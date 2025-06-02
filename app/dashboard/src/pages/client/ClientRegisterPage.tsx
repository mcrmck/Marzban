import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    VStack,
    Text,
    useToast,
    Container,
    Heading,
    Code,
    HStack,
    IconButton,
    useClipboard,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../store/clientPortalStore";
import { CheckIcon, CopyIcon } from "@chakra-ui/icons";

export const ClientRegisterPage = () => {
    const navigate = useNavigate();
    const toast = useToast();
    const { register, isLoadingAuth, error } = useClientPortalStore();
    const [accountNumber, setAccountNumber] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const success = await register();
            if (success) {
                toast({
                    title: "Account Created",
                    description: "Your account has been created successfully.",
                    status: "success",
                    duration: 5000,
                    isClosable: true,
                });
                navigate("/account", { replace: true });
            }
        } catch (err) {
            toast({
                title: "Registration Failed",
                description: error || "Failed to create account. Please try again.",
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
                    <Heading size="xl" mb={2}>Create Your Account</Heading>
                    <Text color="gray.600">Click the button below to create your account</Text>
                </Box>

                <form onSubmit={handleSubmit}>
                    <VStack spacing={4}>
                        <Button
                            type="submit"
                            colorScheme="blue"
                            size="lg"
                            width="full"
                            isLoading={isLoadingAuth}
                            loadingText="Creating account..."
                        >
                            Create Account
                        </Button>

                        <Text fontSize="sm" color="gray.500">
                            Already have an account?{" "}
                            <Button
                                variant="link"
                                color="blue.500"
                                onClick={() => navigate("/login")}
                            >
                                Login here
                            </Button>
                        </Text>
                    </VStack>
                </form>
            </VStack>
        </Container>
    );
};