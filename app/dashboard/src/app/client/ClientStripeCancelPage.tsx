import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    Container,
    Heading,
    Text,
    VStack,
} from "@chakra-ui/react";

const ClientStripeCancelPage = () => {
    const navigate = useNavigate();

    return (
        <Container maxW="container.sm" py={10}>
            <VStack gap={8} textAlign="center">
                <Box>
                    <Heading size="xl" color="orange.500" mb={4}>
                        Payment Cancelled
                    </Heading>
                    <Text color="gray.600" fontSize="lg">
                        Your payment was cancelled. You can try again when you're ready.
                    </Text>
                </Box>

                <Button
                    colorScheme="blue"
                    size="lg"
                    onClick={() => navigate("/portal/plans")}
                >
                    Back to Plans
                </Button>
            </VStack>
        </Container>
    );
};

export default ClientStripeCancelPage;
