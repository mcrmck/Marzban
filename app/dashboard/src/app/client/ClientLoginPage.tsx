import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
    Box,
    Button,
    VStack,
    Text,
    Container,
    Heading,
    Field,
    Input,
} from "@chakra-ui/react";
import { toaster, Toaster } from "../../components/shared/ui/toaster";
import { useClientPortalStore } from "../../lib/stores";
import { useTranslation } from "react-i18next";

interface LocationState {
    from?: {
        pathname: string;
    };
}

const ClientLoginPage = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    const { login, isLoadingAuth, error, isAuthenticated } = useClientPortalStore();
    const [accountNumber, setAccountNumber] = useState("");
    const [formError, setFormError] = useState("");

    useEffect(() => {
        if (isAuthenticated) {
            // Get the location they were trying to go to, or default to account page
            const from = (location.state as LocationState)?.from?.pathname || "/account";
            navigate(from, { replace: true });
        }
    }, [isAuthenticated, navigate, location]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!accountNumber.trim()) {
            setFormError(t("login.fieldRequired"));
            return;
        }
        try {
            await login(accountNumber);
            // Navigation will be handled by the useEffect above
        } catch (err) {
            toaster.create({
                title: t("login.loginFailed"),
                description: error || t("client.noAccountFound"),
                type: "error",
                duration: 5000,
                closable: true,
            });
        }
    };

    return (
        <>
            <Toaster />
            <Container maxW="container.sm" py={10}>
                <VStack gap={8} align="stretch">
                    <Box textAlign="center">
                        <Heading size="xl" mb={2}>{t("client.portal")}</Heading>
                        <Text color="gray.600">{t("client.loginPrompt")}</Text>
                    </Box>

                    <Box as="form" onSubmit={handleSubmit}>
                        <VStack gap={4}>
                            <Field.Root invalid={!!formError}>
                                <Field.Label>{t("client.accountNumber")}</Field.Label>
                                <Input
                                    type="text"
                                    value={accountNumber}
                                    onChange={(e) => {
                                        setAccountNumber(e.target.value);
                                        setFormError("");
                                    }}
                                    placeholder={t("client.loginPrompt")}
                                    size="lg"
                                />
                                {formError && <Field.ErrorText>{formError}</Field.ErrorText>}
                            </Field.Root>

                            <Button
                                type="submit"
                                colorPalette="brand"
                                size="lg"
                                width="full"
                                loading={isLoadingAuth}
                                loadingText={t("loading")}
                            >
                                {t("client.loginButton")}
                            </Button>

                            <Text fontSize="sm" color="gray.500">
                                Need help? Contact support for assistance.
                            </Text>
                        </VStack>
                    </Box>
                </VStack>
            </Container>
        </>
    );
};

export default ClientLoginPage;
