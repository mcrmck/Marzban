import { Box, BoxProps, Text } from "@chakra-ui/react";
import {
  ChartBarIcon,
  ChartPieIcon,
  UsersIcon,
} from "@heroicons/react/24/outline";
import { useDashboard } from "../lib/stores/DashboardContext";
import { FC, PropsWithChildren, ReactElement, ReactNode, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { fetch } from "../lib/api/http";
import { formatBytes, numberWithCommas } from "../lib/utils/formatByte";

// Define the system data type
interface SystemData {
  users_active: number;
  total_user: number;
  incoming_bandwidth: number;
  outgoing_bandwidth: number;
  mem_used: number;
  mem_total: number;
  version: string;
}

// Styled icon components using Box instead of chakra()
const IconWrapper: FC<{ children: ReactElement }> = ({ children }) => (
  <Box
    w={5}
    h={5}
    position="relative"
    zIndex={2}
  >
    {children}
  </Box>
);

type StatisticCardProps = {
  title: string;
  content: ReactNode;
  icon: ReactElement;
};

const StatisticCard: FC<PropsWithChildren<StatisticCardProps>> = ({
  title,
  content,
  icon,
}) => {
  return (
    <Box
      p={6}
      borderWidth="1px"
      borderColor="gray.200"
      bg="gray.50"
      _dark={{ borderColor: "gray.600", bg: "gray.750" }}
      borderStyle="solid"
      boxShadow="none"
      borderRadius="12px"
      width="full"
      display="flex"
      justifyContent="space-between"
      flexDirection="row"
    >
      <Box display="flex" alignItems="center" gap={4}>
        <Box
          p={2}
          position="relative"
          color="white"
          _before={{
            content: `""`,
            position: "absolute",
            top: 0,
            left: 0,
            bg: "blue.400",
            display: "block",
            w: "full",
            h: "full",
            borderRadius: "5px",
            opacity: 0.5,
            zIndex: 1,
          }}
          _after={{
            content: `""`,
            position: "absolute",
            top: "-5px",
            left: "-5px",
            bg: "blue.400",
            display: "block",
            w: "calc(100% + 10px)",
            h: "calc(100% + 10px)",
            borderRadius: "8px",
            opacity: 0.4,
            zIndex: 1,
          }}
        >
          <IconWrapper>{icon}</IconWrapper>
        </Box>
        <Text
          color="gray.600"
          _dark={{
            color: "gray.300",
          }}
          fontWeight="medium"
          textTransform="capitalize"
          fontSize="sm"
        >
          {title}
        </Text>
      </Box>
      <Box fontSize="3xl" fontWeight="semibold" mt={2}>
        {content}
      </Box>
    </Box>
  );
};

export const StatisticsQueryKey = ["statistics-query-key"];

export const Statistics: FC<BoxProps> = (props) => {
  const { version } = useDashboard();
  const { data: systemData } = useQuery<SystemData, Error, SystemData>({
    queryKey: StatisticsQueryKey,
    queryFn: () => fetch.get<SystemData>("/system"),
    refetchInterval: 5000,
  });

  // Update version when data changes
  useEffect(() => {
    if (systemData && version !== systemData.version) {
      useDashboard.setState({ version: systemData.version });
    }
  }, [systemData, version]);

  const { t } = useTranslation();

  return (
    <Box
      display="grid"
      gridTemplateColumns={{ base: "1fr", lg: "repeat(3, 1fr)" }}
      gap={4}
      {...props}
    >
      <StatisticCard
        title={t("activeUsers")}
        content={
          systemData && (
            <Box display="flex" alignItems="flex-end">
              <Text>{numberWithCommas(systemData.users_active)}</Text>
              <Text
                fontWeight="normal"
                fontSize="lg"
                as="span"
                display="inline-block"
                pb="5px"
              >
                / {numberWithCommas(systemData.total_user)}
              </Text>
            </Box>
          )
        }
        icon={<UsersIcon />}
      />
      <StatisticCard
        title={t("dataUsage")}
        content={
          systemData &&
          formatBytes(
            systemData.incoming_bandwidth + systemData.outgoing_bandwidth
          )
        }
        icon={<ChartBarIcon />}
      />
      <StatisticCard
        title={t("memoryUsage")}
        content={
          systemData && (
            <Box display="flex" alignItems="flex-end">
              <Text>{formatBytes(systemData.mem_used, 1, true)[0]}</Text>
              <Text
                fontWeight="normal"
                fontSize="lg"
                as="span"
                display="inline-block"
                pb="5px"
              >
                {formatBytes(systemData.mem_used, 1, true)[1]} /{" "}
                {formatBytes(systemData.mem_total, 1)}
              </Text>
            </Box>
          )
        }
        icon={<ChartPieIcon />}
      />
    </Box>
  );
};