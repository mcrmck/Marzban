/* ----------------------------------------------------------------------
 * Login.tsx – Chakra UI v3 compatible
 * ------------------------------------------------------------------- */

import {
  Alert,
  Box,
  Button,
  Field,
  HStack,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react";
import { ArrowRightOnRectangleIcon } from "@heroicons/react/24/outline";
import { zodResolver } from "@hookform/resolvers/zod";
import { FC, useEffect, useState } from "react";
import { FieldValues, useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { Footer } from "../../components/shared/Footer";
import { fetch } from "../../lib/api/http";
import {
  removeAuthToken,
  setAuthToken,
} from "../../lib/utils/authStorage";

import Logo from "../../assets/logo.svg?react";
import { useTranslation } from "react-i18next";
import { Language } from "../../components/shared/Language";

/* ------------------------------------------------------------------- */
/* Validation schema                                                   */
/* ------------------------------------------------------------------- */
const schema = z.object({
  username: z.string().min(1, "login.fieldRequired"),
  password: z.string().min(1, "login.fieldRequired"),
});

/* ------------------------------------------------------------------- */
/* Small icon components                                               */
/* ------------------------------------------------------------------- */
const LoginIcon: FC<{ className?: string }> = (props) => (
  <ArrowRightOnRectangleIcon
    {...props}
    className={`h-5 w-5 stroke-[2px] ${props.className ?? ""}`}
  />
);

/* ------------------------------------------------------------------- */
/* Page component                                                      */
/* ------------------------------------------------------------------- */
const Login: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  /* form -------------------------------------------------------------- */
  const {
    register,
    formState: { errors },
    handleSubmit,
  } = useForm({
    resolver: zodResolver(schema),
  });

  /* kick unauthenticated users to /login ----------------------------- */
  useEffect(() => {
    removeAuthToken();
    if (location.pathname !== "/login") navigate("/login", { replace: true });
  }, []);

  /* submit handler ---------------------------------------------------- */
  const login = (values: FieldValues) => {
    setError("");
    const formData = new FormData();
    formData.append("username", values.username);
    formData.append("password", values.password);
    formData.append("grant_type", "password");

    setLoading(true);
    fetch.post<{ access_token: string }>("/token", formData)
      .then(({ access_token: token }) => {
        setAuthToken(token);
        // Redirect to admin dashboard root
        window.location.href = "http://localhost:3000/admin/#/";
      })
      .catch((err: any) => setError(err?.response?._data?.detail ?? "Error"))
      .finally(() => setLoading(false));
  };

  /* ------------------------------------------------------------------ */
  /* JSX                                                                */
  /* ------------------------------------------------------------------ */
  return (
    <VStack minH="100vh" w="full" p={6} justify="space-between">
      {/* ---------------------------------------------------------------- */}
      {/* Header / form                                                   */}
      {/* ---------------------------------------------------------------- */}
      <Box w="full">
        {/* language switcher */}
        <HStack justify="flex-end">
          <Language />
        </HStack>

        {/* logo + form */}
        <HStack justify="center">
          <Box w="full" maxW="340px" mt={6}>
            <VStack>
              <Logo width={48} height={48} />
              <Text fontSize="2xl" fontWeight="semibold">
                {t("login.title")}
              </Text>
              <Text color="gray.600" _dark={{ color: "gray.400" }}>
                {t("login.welcomeBack")}
              </Text>
            </VStack>

            {/* form ---------------------------------------------------- */}
            <Box maxW="300px" mx="auto" pt={4}>
              <form onSubmit={handleSubmit(login)}>
                <VStack gap={2}>
                  {/* username */}
                  <Field.Root invalid={!!errors.username}>
                    <Field.Label>{t("username")}</Field.Label>
                    <Input
                      placeholder={t("username")}
                      {...register("username")}
                    />
                    {errors.username && (
                      <Field.ErrorText>
                        {t(errors.username.message as string)}
                      </Field.ErrorText>
                    )}
                  </Field.Root>

                  {/* password */}
                  <Field.Root invalid={!!errors.password}>
                    <Field.Label>{t("password")}</Field.Label>
                    <Input
                      type="password"
                      placeholder={t("password")}
                      {...register("password")}
                    />
                    {errors.password && (
                      <Field.ErrorText>
                        {t(errors.password.message as string)}
                      </Field.ErrorText>
                    )}
                  </Field.Root>

                  {/* api / auth error */}
                  {error && (
                    <Alert.Root status="error" borderRadius="md">
                      <Alert.Description>{error}</Alert.Description>
                    </Alert.Root>
                  )}

                  {/* submit */}
                  <Button
                    type="submit"
                    w="full"
                    colorPalette="primary"
                    loading={loading}
                  >
                    <LoginIcon className="me-1" />
                    {t("loginButton")}
                  </Button>
                </VStack>
              </form>
            </Box>
          </Box>
        </HStack>
      </Box>

      {/* footer */}
      <Footer />
    </VStack>
  );
};

export default Login;
