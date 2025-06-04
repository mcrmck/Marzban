import {
  Box,
  chakra,
  HStack,
  IconButton,
  Menu,
  Text,
} from "@chakra-ui/react";
import { useTheme } from "next-themes";
import {
  ArrowLeftOnRectangleIcon,
  Bars3Icon,
  ChartPieIcon,
  Cog6ToothIcon,
  DocumentMinusIcon,
  MoonIcon,
  SunIcon,
} from "@heroicons/react/24/outline";
import { useDashboard } from "../lib/stores/DashboardContext";
import { FC, ReactNode } from "react";
import GitHubButton from "react-github-btn";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { updateThemeColor } from "../lib/utils/themeColor";
import { Language } from "./Language";
import useGetUser from "../lib/hooks/useGetUser";
import { REPO_URL } from "constants/Project";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const Icon4 = <T extends { className?: string }>(Icon: FC<T>) =>
  chakra(Icon);

const DarkIcon        = Icon4(MoonIcon);
const LightIcon       = Icon4(SunIcon);
const CoreSettingsIcon= Icon4(Cog6ToothIcon);
const SettingsIcon    = Icon4(Bars3Icon);
const LogoutIcon      = Icon4(ArrowLeftOnRectangleIcon);
const NodesUsageIcon  = Icon4(ChartPieIcon);
const ResetUsageIcon  = Icon4(DocumentMinusIcon);

type HeaderProps = { actions?: ReactNode };

export const Header: FC<HeaderProps> = () => {
  /* data ---------------------------------------------------------------- */
  const { data: userData, isSuccess, isPending } = useGetUser();
  const isSudo = !isPending && isSuccess && userData?.is_sudo;

  const { onResetAllUsage, onShowingNodesUsage } = useDashboard();
  const { t } = useTranslation();

  const { theme, setTheme } = useTheme();
  const gBtnColor = theme === "dark" ? "dark_dimmed" : theme;

  /* render -------------------------------------------------------------- */
  return (
    <HStack gap={2} justify="space-between" position="relative">
      <Text as="h1" fontWeight="semibold" fontSize="2xl">
        {t("users")}
      </Text>

      <Box overflow="auto" css={{ direction: "rtl" }}>
        <HStack align="center">
          {/* settings menu ------------------------------------------------ */}
          <Menu.Root>
            <Menu.Trigger asChild>
              <IconButton
                size="sm"
                variant="outline"
                aria-label="settings"
              >
                <SettingsIcon />
              </IconButton>
            </Menu.Trigger>

            <Menu.Content minW="170px" zIndex={9_999} className="menuList">
              {isSudo && (
                <>
                  <Menu.Item
                    value="nodes-usage"
                    onClick={() => onShowingNodesUsage(true)}
                    fontSize="sm"
                    maxW="170px"
                  >
                    <HStack>
                      <NodesUsageIcon />
                      <Text>{t("header.nodesUsage")}</Text>
                    </HStack>
                  </Menu.Item>

                  <Menu.Item
                    value="reset-usage"
                    onClick={() => onResetAllUsage(true)}
                    fontSize="sm"
                    maxW="170px"
                  >
                    <HStack>
                      <ResetUsageIcon />
                      <Text>{t("resetAllUsage")}</Text>
                    </HStack>
                  </Menu.Item>
                </>
              )}

              <Link to="/login">
                <Menu.Item value="logout" fontSize="sm" maxW="170px">
                  <HStack>
                    <LogoutIcon />
                    <Text>{t("header.logout")}</Text>
                  </HStack>
                </Menu.Item>
              </Link>
            </Menu.Content>
          </Menu.Root>

          {/* core-settings button ---------------------------------------- */}
          {isSudo && (
            <IconButton
              size="sm"
              variant="outline"
              aria-label="core settings"
              onClick={() => useDashboard.setState({ isEditingCore: true })}
            >
              <CoreSettingsIcon />
            </IconButton>
          )}

          {/* language picker --------------------------------------------- */}
          <Language />

          {/* light / dark toggle ----------------------------------------- */}
          <IconButton
            size="sm"
            variant="outline"
            aria-label="switch theme"
            onClick={() => {
              const next = theme === "dark" ? "light" : "dark";
              updateThemeColor(next);
              setTheme(next);
            }}
          >
            {theme === "light" ? <DarkIcon /> : <LightIcon />}
          </IconButton>


        </HStack>
      </Box>
    </HStack>
  );
};
