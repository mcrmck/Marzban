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
    useToast,
    Spinner,
    Alert,
    AlertIcon,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../store/clientPortalStore";
import { ClientPlan } from "../../types/clientPortal";

interface PlanCardProps {
    plan: ClientPlan;
    onSelect: (planId: string) => Promise<void>;
    isLoading: boolean;
}

const PlanCard = ({ plan, onSelect, isLoading }: PlanCardProps) => (
    <Box
        borderWidth="1px"
        borderRadius="lg"
        p={6}
        shadow="md"
        _hover={{ shadow: "lg" }}
        transition="all 0.2s"
    >
        <VStack spacing={4} align="stretch">
            <Heading size="md">{plan.name}</Heading>
            <Text fontSize="2xl" fontWeight="bold">
                ${plan.price}/month
            </Text>
            <Text color="gray.600">{plan.description}</Text>
            <VStack align="stretch" spacing={2}>
                {plan.features.map((feature, index) => (
                    <Text key={index}>• {feature}</Text>
                ))}
            </VStack>
            <Button
                colorScheme="blue"
                onClick={() => onSelect(plan.id)}
                isLoading={isLoading}
                loadingText="Processing..."
            >
                Select Plan
            </Button>
        </VStack>
    </Box>
);

export const ClientPlansPage = () => {
    const navigate = useNavigate();
    const toast = useToast();
    const {
        plans,
        fetchPlans,
        isLoadingPlans,
        initiateStripeCheckout,
        activatePlanDirectly,
        isAuthenticated,
    } = useClientPortalStore();

    useEffect(() => {
        fetchPlans();
    }, [fetchPlans]);

    const handlePlanSelect = async (planId: string) => {
        try {
            const plan = plans.find((p) => p.id === planId);
            if (!plan) return;

            if (plan.stripe_price_id) {
                const response = await initiateStripeCheckout(planId);
                if (response?.url) {
                    window.location.href = response.url;
                }
            } else {
                await activatePlanDirectly(planId);
                toast({
                    title: "Plan Activated",
                    description: "Your plan has been successfully activated.",
                    status: "success",
                    duration: 5000,
                    isClosable: true,
                });
                navigate("/portal/account");
            }
        } catch (error) {
            toast({
                title: "Error",
                description: "Failed to process plan selection. Please try again.",
                status: "error",
                duration: 5000,
                isClosable: true,
            });
        }
    };

    if (isLoadingPlans) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    return (
        <Container maxW="container.xl" py={10}>
            <VStack spacing={8}>
                <Box textAlign="center">
                    <Heading size="xl" mb={2}>Subscription Plans</Heading>
                    <Text color="gray.600">
                        Choose the plan that best fits your needs
                    </Text>
                </Box>

                {!isAuthenticated && (
                    <Alert status="info">
                        <AlertIcon />
                        Please log in to subscribe to a plan
                    </Alert>
                )}

                <Grid
                    templateColumns={{
                        base: "1fr",
                        md: "repeat(2, 1fr)",
                        lg: "repeat(3, 1fr)",
                    }}
                    gap={6}
                >
                    {plans.map((plan) => (
                        <PlanCard
                            key={plan.id}
                            plan={plan}
                            onSelect={handlePlanSelect}
                            isLoading={isLoadingPlans}
                        />
                    ))}
                </Grid>
            </VStack>
        </Container>
    );
};