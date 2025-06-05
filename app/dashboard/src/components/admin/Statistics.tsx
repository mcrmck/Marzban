import { Box, BoxProps, Text } from "@chakra-ui/react";
import {
  ChartBarIcon,
  ChartPieIcon,
  UsersIcon,
} from "@heroicons/react/24/outline";
import { useDashboard } from "../../lib/stores/DashboardContext";
import { FC, PropsWithChildren, ReactElement, ReactNode, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { fetch } from "../../lib/api/http";
import { formatBytes, numberWithCommas } from "../../lib/utils/formatByte";

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
      bg="white"
      _dark={{ borderColor: "gray.600", bg: "gray.800" }}
      borderStyle="solid"
      boxShadow="sm"
      borderRadius="lg"
      width="full"
      transition="all 0.2s"
      _hover={{
        boxShadow: "md",
        transform: "translateY(-1px)"
      }}
    >
      <Box display="flex" alignItems="center" gap={3} mb={4}>
        <Box
          p={3}
          bg="blue.500"
          borderRadius="lg"
          color="white"
          display="flex"
          alignItems="center"
          justifyContent="center"
        >
          <IconWrapper>{icon}</IconWrapper>
        </Box>
        <Text
          color="gray.600"
          _dark={{
            color: "gray.300",
          }}
          fontWeight="medium"
          fontSize="sm"
          lineHeight="1.2"
        >
          {title}
        </Text>
      </Box>
      <Box 
        fontSize="2xl" 
        fontWeight="bold" 
        color="gray.900"
        _dark={{ color: "white" }}
        lineHeight="1.2"
      >
        {content || "—"}
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
      gridTemplateColumns={{ base: "1fr", md: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" }}
      gap={6}
      {...props}
    >
      <StatisticCard
        title={t("activeUsers")}
        content={
          systemData && (
            <Box display="flex" alignItems="baseline" gap={1}>
              <Text fontSize="2xl" fontWeight="bold">{numberWithCommas(systemData.users_active)}</Text>
              <Text
                fontSize="md"
                fontWeight="medium"
                color="gray.500"
                _dark={{ color: "gray.400" }}
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
            <Box display="flex" alignItems="baseline" gap={1}>
              <Text fontSize="2xl" fontWeight="bold">
                {formatBytes(systemData.mem_used, 1, true)[0]}
                <Text as="span" fontSize="sm" fontWeight="medium" color="gray.500">
                  {formatBytes(systemData.mem_used, 1, true)[1]}
                </Text>
              </Text>
              <Text
                fontSize="md"
                fontWeight="medium"
                color="gray.500"
                _dark={{ color: "gray.400" }}
              >
                / {formatBytes(systemData.mem_total, 1)}
              </Text>
            </Box>
          )
        }
        icon={<ChartPieIcon />}
      />
    </Box>
  );
};