import {
  Box,
  Button,
  Flex,
  HStack,
  IconButton,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Text,
  useColorMode,
} from "@chakra-ui/react";
import {
  ArrowLeftOnRectangleIcon,
  MoonIcon,
  SunIcon,
  UserCircleIcon,
} from "@heroicons/react/24/outline";
import { chakra } from "@chakra-ui/react";
import { FC } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { updateThemeColor } from "utils/themeColor";
import { Language } from "../Language";
import useGetUser from "hooks/useGetUser";
import { User } from "../../types/User";

const iconProps = {
  baseStyle: {
    w: 4,
    h: 4,
  },
};

const DarkIcon = chakra(MoonIcon, iconProps);
const LightIcon = chakra(SunIcon, iconProps);
const LogoutIcon = chakra(ArrowLeftOnRectangleIcon, iconProps);
const UserIcon = chakra(UserCircleIcon, iconProps);

export const ClientHeader: FC = () => {
  const { t } = useTranslation();
  const { colorMode, toggleColorMode } = useColorMode();
  const location = useLocation();
  const navigate = useNavigate();
  const { userData, getUserIsSuccess } = useGetUser();

  const isActive = () => {
    const user = userData as unknown as User;
    return user?.status === "active";
  };

  const navItems = [
    { path: "/", label: t("home") },
    { path: "/plans", label: t("plans") },
    { path: "/servers", label: t("servers") },
    { path: "/account", label: t("account") },
  ];

  return (
    <Box as="header" py={4} px={6} borderBottom="1px" borderColor="gray.200">
      <Flex justify="space-between" align="center">
        <HStack spacing={8}>
          {navItems.map((item) => (
            <Link key={item.path} to={item.path}>
              <Text
                fontWeight={location.pathname === item.path ? "bold" : "normal"}
                color={location.pathname === item.path ? "brand.500" : "inherit"}
              >
                {item.label}
              </Text>
            </Link>
          ))}
        </HStack>

        <HStack spacing={4}>
          {!getUserIsSuccess ? (
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
              <Menu>
                <MenuButton
                  as={IconButton}
                  icon={<UserIcon />}
                  variant="ghost"
                />
                <MenuList>
                  <MenuItem
                    icon={<LogoutIcon />}
                    onClick={() => navigate("/login")}
                  >
                    {t("logout")}
                  </MenuItem>
                </MenuList>
              </Menu>
            </>
          )}

          <Language />

          <IconButton
            size="sm"
            variant="ghost"
            aria-label="switch theme"
            onClick={() => {
              updateThemeColor(colorMode === "dark" ? "light" : "dark");
              toggleColorMode();
            }}
          >
            {colorMode === "light" ? <DarkIcon /> : <LightIcon />}
          </IconButton>
        </HStack>
      </Flex>
    </Box>
  );
};