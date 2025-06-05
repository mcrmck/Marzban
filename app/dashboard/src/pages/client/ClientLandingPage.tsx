import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    Container,
    Heading,
    Text,
    VStack,
    SimpleGrid,
    Icon,
    Spinner,
} from "@chakra-ui/react";
import { FaServer, FaCreditCard, FaUser } from "react-icons/fa";
import { useClientPortalStore } from "../../lib/stores";
import { toaster } from "../../components/shared/ui/toaster";
import { useTranslation } from "react-i18next";

const FeatureCard = ({ icon, title, description, onClick }: {
    icon: any;
    title: string;
    description: string;
    onClick: () => void;
}) => (
    <Box
        p={6}
        borderWidth="1px"
        borderRadius="lg"
        bg="white"
        shadow="sm"
        _hover={{ shadow: "md" }}
        cursor="pointer"
        onClick={onClick}
    >
        <VStack align="start" gap={4}>
            <Icon as={icon} w={8} h={8} color="blue.500" />
            <Heading size="md">{title}</Heading>
            <Text color="gray.600">{description}</Text>
        </VStack>
    </Box>
);

export const ClientLandingPage = () => {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { clientDetails, fetchClientDetails, isLoadingDetails } = useClientPortalStore();

    useEffect(() => {
        fetchClientDetails().catch(() => {
            toaster.create({
                title: t("error"),
                description: t("client.fetchDetailsError"),
                type: "error",
                duration: 5000,
                closable: true,
            });
        });
    }, [fetchClientDetails, t]);

    if (isLoadingDetails) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    return (
        <Container maxW="container.xl" py={10}>
            <VStack gap={8} align="stretch">
                <Box>
                    <Heading size="xl">{t("client.welcome")}</Heading>
                    <Text color="gray.600" mt={2}>
                        {t("client.manageServices")}
                    </Text>
                </Box>

                <SimpleGrid columns={{ base: 1, md: 3 }} gap={6}>
                    <FeatureCard
                        icon={FaServer}
                        title={t("client.servers")}
                        description={t("client.serversDescription")}
                        onClick={() => navigate("/servers")}
                    />
                    <FeatureCard
                        icon={FaCreditCard}
                        title={t("client.plans")}
                        description={t("client.plansDescription")}
                        onClick={() => navigate("/plans")}
                    />
                    <FeatureCard
                        icon={FaUser}
                        title={t("client.account")}
                        description={t("client.accountDescription")}
                        onClick={() => navigate("/account")}
                    />
                </SimpleGrid>

                {clientDetails?.user.status === "inactive" && (
                    <Box
                        p={6}
                        borderWidth="1px"
                        borderRadius="lg"
                        bg="yellow.50"
                        borderColor="yellow.200"
                    >
                        <VStack align="start" gap={4}>
                            <Heading size="md" color="yellow.700">
                                {t("client.accountInactive")}
                            </Heading>
                            <Text color="yellow.700">
                                {t("client.accountInactiveDescription")}
                            </Text>
                            <Button
                                colorScheme="yellow"
                                onClick={() => navigate("/plans")}
                            >
                                {t("client.viewPlans")}
                            </Button>
                        </VStack>
                    </Box>
                )}
            </VStack>
        </Container>
    );
};