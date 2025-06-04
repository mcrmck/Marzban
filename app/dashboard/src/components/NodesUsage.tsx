// components/NodesUsage.tsx
import {
  Box,
  Dialog,            // ← new Modal replacement
  HStack,
  VStack,
  Text,
  IconButton,
  Spinner,             // ← CircularProgress → Spinner
  chakra,
  Icon,
} from "@chakra-ui/react";
import { useTheme }            from "next-themes";   // ← useColorMode is gone
import { ChartPieIcon }        from "@heroicons/react/24/outline";
import { FilterUsageType, useDashboard } from "../lib/stores/DashboardContext";
import { useNodes }            from "../lib/stores/NodesContext";
import dayjs                   from "dayjs";
import { FC, Suspense, useEffect, useState } from "react";
import ReactApexChart          from "react-apexcharts";
import { useTranslation }      from "react-i18next";
import { UsageFilter, createUsageConfig } from "./UsageFilter";

/* ---------------- icon wrapper (chakra v3 pattern) ----------- */
const StatusIcon = chakra(ChartPieIcon);

/* --------------------------------------------------------------------- */
export const NodesUsage: FC = () => {
  const { t } = useTranslation();

  /* ---------- Chakra v3: Dialog instead of Modal -------------------- */
  const { isShowingNodesUsage, onShowingNodesUsage } = useDashboard();
  const closeDialog = () => {
    onShowingNodesUsage(false);
    setCurrentFilter("1m");
  };

  /* ---------- color mode comes from next-themes --------------------- */
  const { theme } = useTheme();
  const colorMode = theme === "dark" ? "dark" : "light";

  /* ---------- usage data / chart state ------------------------------ */
  const { fetchNodesUsage } = useNodes();
  const title = t("userDialog.total");

  const [chart, setChart] = useState(createUsageConfig(title));
  const [currentFilter, setCurrentFilter] = useState<"1m" | "3m" | "6m">("1m");
  const [fetching, setFetching] = useState(false);

  const loadUsage = async (query: FilterUsageType) => {
    setFetching(true);
    try {
      const data = await fetchNodesUsage(query);

      const series = Object.values(data.usages).map(
        (u: any) => u.uplink + u.downlink
      );
      const labels = Object.values(data.usages).map(
        (u: any) => u.node_name
      );

      setChart(createUsageConfig(title, series, labels));
    } finally {
      setFetching(false);
    }
  };

  /* initial fetch when dialog opens */
  useEffect(() => {
    if (isShowingNodesUsage) {
      loadUsage({
        start: dayjs().utc().subtract(30, "day").format("YYYY-MM-DDTHH:00:00"),
      });
    }
  }, [isShowingNodesUsage]);

  /* ------------------------------- UI ------------------------------- */
  return (
    <Dialog.Root open={isShowingNodesUsage} onOpenChange={closeDialog}>
      <Dialog.Backdrop bg="blackAlpha.300" backdropFilter="blur(10px)" />
      <Dialog.Content mx="3" w="full" maxW="2xl">
        <Dialog.Header pt={6}>
          <HStack gap={2}>
            <Icon color="primary">
              <StatusIcon w={5} h={5} color="white" />
            </Icon>
            <Text fontWeight="semibold" fontSize="lg">
              {t("header.nodesUsage")}
            </Text>
          </HStack>
        </Dialog.Header>

        {/* Dialog.CloseTrigger replaces ModalCloseButton */}
        <Dialog.CloseTrigger asChild>
          <IconButton
            aria-label="close"
            size="sm"
            variant="ghost"
            pos="absolute"
            top="3"
            right="3"
            disabled={fetching}
          >
            <span>&times;</span>
          </IconButton>
        </Dialog.CloseTrigger>

        <Dialog.Body>
          <VStack gap={4}>
            <UsageFilter
              defaultValue={currentFilter}
              onChange={(flt, q) => {
                setCurrentFilter(flt as any);
                loadUsage(q);
              }}
            />
            <Box w="full" maxW="300px" mt={4}>
              <Suspense fallback={<Spinner />}>
                <ReactApexChart
                  options={chart.options}
                  series={chart.series}
                  type="donut"
                  height={500}
                />
              </Suspense>
            </Box>
          </VStack>
        </Dialog.Body>

        <Dialog.Footer />
      </Dialog.Content>
    </Dialog.Root>
  );
};
