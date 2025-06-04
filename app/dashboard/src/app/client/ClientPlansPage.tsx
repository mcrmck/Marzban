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
    Spinner,
    Alert,
    AlertIndicator,
    AlertContent,
    AlertTitle,
    AlertDescription,
} from "@chakra-ui/react";
import { Toaster } from "@/components/ui/toaster";
import { toaster } from "@/components/ui/toaster";
import { useClientPortalStore } from "../../lib/stores";
import { ClientPlan } from "../../lib/types";

interface PlanCardProps {
    plan: ClientPlan;
    onSelect: (planId: string) => Promise<void>;
    isLoading: boolean;
}

const PlanCard = ({ plan, onSelect, isLoading }: PlanCardProps) => {
    return (
        <Box
            borderWidth="1px"
            borderRadius="lg"
            p="6"
            bg="white"
            _dark={{ bg: "gray.700" }}
        >
            <VStack align="start" gap={4}>
                <Heading size="md">{plan.name}</Heading>
                <Text fontSize="2xl" fontWeight="bold">
                    ${plan.price}
                    <Text as="span" fontSize="md" fontWeight="normal">
                        /month
                    </Text>
                </Text>
                <Text color="gray.600" _dark={{ color: "gray.300" }}>
                    {plan.description}
                </Text>
                <Button
                    colorScheme="brand"
                    width="full"
                    onClick={() => onSelect(plan.id)}
                    loading={isLoading}
                >
                    Select Plan
                </Button>
            </VStack>
        </Box>
    );
};

const ClientPlansPage = () => {
    return (
        <>
            <Toaster />
            <ClientPlansPageContent />
        </>
    );
};

const ClientPlansPageContent = () => {
    const navigate = useNavigate();
    const {
        plans,
        fetchPlans,
        isLoadingPlans,
        initiateStripeCheckout,
        activatePlanDirectly,
        isAuthenticated
    } = useClientPortalStore();
    // createToast is now imported directly

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
                toaster.create({
                    title: "Plan Activated",
                    description: "Your plan has been successfully activated.",
                    type: "success",
                    duration: 5000,
                    closable: true,
                });
                navigate("/account");
            }
        } catch (error) {
            toaster.create({
                title: "Error",
                description: "Failed to process plan selection. Please try again.",
                type: "error",
                duration: 5000,
                closable: true,
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

    if (!plans.length) {
        return (
            <Container maxW="container.md" py={10}>
                <Alert.Root status="info">
                    <AlertIndicator />
                    <AlertContent>
                        <AlertTitle>No Plans Available</AlertTitle>
                        <AlertDescription>
                            There are currently no subscription plans available. Please check back later.
                        </AlertDescription>
                    </AlertContent>
                </Alert.Root>
            </Container>
        );
    }

    return (
        <Container maxW="container.xl" py={10}>
            <VStack gap={8} align="stretch">
                <Box textAlign="center">
                    <Heading size="xl" mb={2}>Choose Your Plan</Heading>
                    <Text color="gray.600">Select a plan that best fits your needs</Text>
                </Box>

                {!isAuthenticated && (
                    <Alert.Root status="info">
                        <AlertIndicator />
                        <AlertContent>
                            <AlertTitle>Please log in to subscribe to a plan</AlertTitle>
                        </AlertContent>
                    </Alert.Root>
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

export default ClientPlansPage;
