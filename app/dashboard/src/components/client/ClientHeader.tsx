import {
  Box,
  Button,
  Flex,
  HStack,
  IconButton,
  Menu,
  Portal,
  Text,
} from "@chakra-ui/react";
import {
  MoonIcon,
  SunIcon,
  UserCircleIcon,
} from "@heroicons/react/24/outline";
import { FC } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { updateThemeColor } from "../../lib/utils/themeColor";
import { Language } from "../Language";
import { useClientPortalStore } from "../../lib/stores";
import { useTheme } from "next-themes";

const iconStyle = {
  width: "1rem",
  height: "1rem",
};

export const ClientHeader: FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();
  const { clientDetails } = useClientPortalStore();

  const isActive = () => {
    return clientDetails?.user.status === "active";
  };

  return (
    <Box
      as="header"
      position="fixed"
      top={0}
      left={0}
      right={0}
      zIndex="sticky"
      borderBottom="1px"
      borderColor="border.default"
      bg="bg.surface"
      boxShadow="sm"
    >
      <Flex
        h="16"
        alignItems="center"
        justifyContent="space-between"
        px={4}
        maxW="container.xl"
        mx="auto"
      >
        <HStack gap={8}>
          <Link to="/">
            <Text fontSize="xl" fontWeight="bold" color="colorPalette.solid">
              {t("app.name")}
            </Text>
          </Link>
          <HStack gap={4}>
            <Link to="/servers">
              <Text color={theme === "dark" ? "white" : "gray.700"} _hover={{ color: "brand.500" }}>
                {t("client.servers")}
              </Text>
            </Link>
            <Link to="/nodes">
              <Text color={theme === "dark" ? "white" : "gray.700"} _hover={{ color: "brand.500" }}>
                {t("admin.nodes")}
              </Text>
            </Link>
            <Link to="/plans">
              <Text color={theme === "dark" ? "white" : "gray.700"} _hover={{ color: "brand.500" }}>
                {t("client.plans")}
              </Text>
            </Link>
            <Link to="/account">
              <Text color={theme === "dark" ? "white" : "gray.700"} _hover={{ color: "brand.500" }}>
                {t("client.account")}
              </Text>
            </Link>
          </HStack>
        </HStack>

        <HStack gap={4}>
          {!clientDetails ? (
            <>
              <Button
                variant="ghost"
                onClick={() => navigate("/login")}
              >
                {t("login")}
              </Button>
              <Button
                colorScheme="brand"
                onClick={() => navigate("/register")}
              >
                {t("register")}
              </Button>
            </>
          ) : (
            <>
              {!isActive() && (
                <Button
                  colorScheme="orange"
                  onClick={() => navigate("/plans")}
                >
                  {t("activateAccount")}
                </Button>
              )}
              <Menu.Root>
                <Menu.Trigger>
                  <Box
                    as="div"
                    cursor="pointer"
                    p={2}
                    _hover={{ bg: theme === "dark" ? "gray.700" : "gray.100" }}
                    borderRadius="md"
                  >
                    <UserCircleIcon style={iconStyle} />
                  </Box>
                </Menu.Trigger>
                <Portal>
                  <Menu.Positioner>
                    <Menu.Content>
                    </Menu.Content>
                  </Menu.Positioner>
                </Portal>
              </Menu.Root>
            </>
          )}

          <Language />

          <IconButton
            size="sm"
            variant="ghost"
            aria-label="switch theme"
            onClick={() => {
              const newTheme = theme === "dark" ? "light" : "dark";
              updateThemeColor(newTheme);
              setTheme(newTheme);
            }}
          >
            {theme === "light" ? (
              <MoonIcon style={iconStyle} />
            ) : (
              <SunIcon style={iconStyle} />
            )}
          </IconButton>
        </HStack>
      </Flex>
    </Box>
  );
};