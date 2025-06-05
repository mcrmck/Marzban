import {
  Box,
  HStack,
  Icon,
  SimpleGrid,
  Tabs,
  Text,
  VStack,
  useBreakpointValue,
  useDisclosure,
  RadioGroup,
} from "@chakra-ui/react";
import { CalendarIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
import { ApexOptions } from "apexcharts";
import { FilterUsageType } from "../lib/stores/DashboardContext";
import dayjs, { ManipulateType } from "dayjs";
import { FC, useRef, useState, useEffect } from "react";
import ReactDatePicker from "react-datepicker";
import { useTranslation } from "react-i18next";
import { generateDistinctColors } from "../lib/utils/color";
import { formatBytes } from "../lib/utils/formatByte";
import { useTheme } from "next-themes";

// Custom hook for outside click detection
const useOutsideClick = (ref: React.RefObject<HTMLElement | null>, handler: () => void) => {
  useEffect(() => {
    const listener = (event: MouseEvent | TouchEvent) => {
      if (!ref.current || ref.current.contains(event.target as Node)) {
        return;
      }
      handler();
    };

    document.addEventListener('mousedown', listener);
    document.addEventListener('touchstart', listener);

    return () => {
      document.removeEventListener('mousedown', listener);
      document.removeEventListener('touchstart', listener);
    };
  }, [ref, handler]);
};

type DateType = Date | null;

const FilterItem: FC<any> = ({ border, ...props }) => {
  const fontSize = useBreakpointValue({ base: "xs", md: "sm" });
  return (
    <Box as="label">
      <Box
        minW="48px"
        w="full"
        h="full"
        textAlign="center"
        cursor="pointer"
        fontSize={fontSize}
        borderWidth={border ? "1px" : "0px"}
        borderRadius="md"
        _checked={{
          bg: "primary.500",
          color: "white",
          borderColor: "primary.500",
        }}
        _focus={{
          boxShadow: "outline",
        }}
        px={3}
        py={1}
        {...props}
      >
        {props.children}
      </Box>
    </Box>
  );
};

export type UsageFilterProps = {
  onChange: (filter: string, query: FilterUsageType) => void;
  defaultValue: string;
};

export const UsageFilter: FC<UsageFilterProps> = ({
  onChange,
  defaultValue,
  ...props
}) => {
  const { t, i18n } = useTranslation();
  const { theme } = useTheme();

  const filterOptions = useBreakpointValue({
    base: ["7h", "1d", "3d", "1w"],
    md: ["7h", "1d", "3d", "1w", "1m", "3m"],
  })!;
  const filterOptionTypes = {
    h: "hour",
    d: "day",
    w: "week",
    m: "month",
    y: "year",
  };
  const customFilterOptions = useBreakpointValue({
    base: [
      { title: "hours", options: ["1h", "3h", "6h", "12h"] },
      { title: "days", options: ["1d", "2d", "3d", "4d"] },
      { title: "weeks", options: ["1w", "2w", "3w", "4w"] },
      { title: "months", options: ["1m", "2m", "3m", "6m"] },
    ],
    md: [
      { title: "hours", options: ["1h", "2h", "3h", "6h", "8h", "12h"] },
      { title: "days", options: ["1d", "2d", "3d", "4d", "5d", "6d"] },
      { title: "weeks", options: ["1w", "2w", "3w", "4w"] },
      { title: "months", options: ["1m", "2m", "3m", "6m", "8m"] },
    ],
  })!;

  const [selectedValue, setSelectedValue] = useState(defaultValue);

  const handleValueChange = (details: { value: string | null }) => {
    const value = details.value;
    if (!value || value === "custom") {
      return;
    }

    closeCustom();

    if (filterOptions.indexOf(value) >= 0) {
      setCustomLabel(t("userDialog.custom"));
      setCustom(false);
    } else {
      setCustomLabel(t("userDialog.custom") + ` (${value})`);
      setCustom(true);
    }

    const num = Number(value.substring(0, value.length - 1));
    const unit =
      filterOptionTypes[
        value[value.length - 1] as keyof typeof filterOptionTypes
      ];
    onChange(value, {
      start: dayjs()
        .utc()
        .subtract(num, unit as ManipulateType)
        .format("YYYY-MM-DDTHH:00:00"),
    });
    setSelectedValue(value);
  };

  const {
    open: isCustomOpen,
    onOpen: openCustom,
    onClose: closeCustom,
  } = useDisclosure();
  const customRef = useRef<HTMLDivElement>(null);
  useOutsideClick(customRef, closeCustom);

  const [customLabel, setCustomLabel] = useState(t("userDialog.custom"));
  const [custom, setCustom] = useState(false);
  const [tabIndex, setTabIndex] = useState(0);

  const monthsShown = useBreakpointValue({ base: 1, md: 2 });
  const fontSize = useBreakpointValue({ base: "xs", md: "sm" });
  const [startDate, setStartDate] = useState(null as DateType);
  const [endDate, setEndDate] = useState(null as DateType);
  const onDateChange = (dates: [DateType, DateType]) => {
    const [start, end] = dates;
    if (endDate && !end) {
      setStartDate(null);
      setEndDate(null);
    } else {
      setStartDate(start);
      setEndDate(end);
      if (start && end) {
        closeCustom();
        onChange("custom", {
          start: dayjs(start).format("YYYY-MM-DDT00:00:00"),
          end: dayjs(end).format("YYYY-MM-DDT23:59:59"),
        });
      }
    }
  };

  return (
    <VStack {...props}>
      {tabIndex == 0 && (
        <SimpleGrid
          gap={0}
          display="flex"
          borderWidth="1px"
          borderRadius="md"
          minW={{ base: "320px", md: "400px" }}
        >
          <RadioGroup.Root value={selectedValue} onValueChange={handleValueChange}>
            {filterOptions.map((value) => {
              return (
                <FilterItem key={value} value={value}>
                  {value}
                </FilterItem>
              );
            })}
          </RadioGroup.Root>
          <Box
            onClick={() => {
              setStartDate(null);
              setEndDate(null);
              openCustom();
            }}
            cursor="pointer"
            borderRadius="md"
            w="full"
            fontSize={fontSize}
            px={3}
            py={1}
            bg={custom ? "primary.500" : "unset"}
            color={custom ? "white" : "unset"}
            borderColor={custom ? "primary.500" : "unset"}
          >
            <HStack>
              <Text>{customLabel}</Text>
              <Icon as={CalendarIcon} boxSize="18px" />
            </HStack>
          </Box>
        </SimpleGrid>
      )}
      {tabIndex == 1 && (
        <HStack
          onClick={openCustom}
          cursor="pointer"
          fontSize={fontSize}
          borderRadius="md"
          px={3}
          py={1}
          minW={{ base: "320px", md: "400px" }}
          borderWidth="1px"
        >
          <Text w="full" color={startDate ? "unset" : "gray.500"}>
            {startDate
              ? dayjs(startDate).format("YYYY-MM-DD (00:00)")
              : t("userDialog.startDate")}
          </Text>
          <Icon as={ChevronRightIcon} boxSize="18px" />
          <Text w="full" color={endDate ? "unset" : "gray.500"}>
            {endDate
              ? dayjs(endDate).format("YYYY-MM-DD (23:59)")
              : t("userDialog.endDate")}
          </Text>
          <Icon as={CalendarIcon} boxSize="18px" />
        </HStack>
      )}
      <VStack
        ref={customRef}
        marginTop="40px !important"
        borderRadius="md"
        borderWidth="1px"
        position="absolute"
        zIndex="1"
        backgroundColor="white"
        _dark={{
          backgroundColor: "gray.700",
        }}
        display={isCustomOpen ? "unset" : "none"}
      >
        <Tabs.Root defaultValue={tabIndex === 0 ? "relative" : "absolute"} onValueChange={(details) => setTabIndex(details.value === "relative" ? 0 : 1)}>
          <Tabs.List>
            <Tabs.Trigger value="relative">Relative</Tabs.Trigger>
            <Tabs.Trigger value="absolute">Absolute</Tabs.Trigger>
          </Tabs.List>

          <Tabs.Content value="relative">
            {customFilterOptions.map((row) => {
              return (
                <VStack key={row.title} alignItems="start" pl={2} pr={2}>
                  <HStack justifyItems="flex-start" mb={4}>
                    <Text fontSize={fontSize} minW="60px">
                      {t("userDialog." + row.title)}
                    </Text>
                    <RadioGroup.Root value={selectedValue} onValueChange={handleValueChange}>
                      {row.options.map((value: string) => {
                        return (
                          <FilterItem
                            key={value + ".custom"}
                            border={true}
                            value={value}
                          >
                            {value}
                          </FilterItem>
                        );
                      })}
                    </RadioGroup.Root>
                  </HStack>
                </VStack>
              );
            })}
          </Tabs.Content>
          <Tabs.Content value="absolute">
            <VStack>
              <ReactDatePicker
                locale={i18n.language.toLocaleLowerCase()}
                selected={startDate}
                onChange={onDateChange}
                startDate={startDate}
                endDate={endDate}
                selectsRange={true}
                maxDate={new Date()}
                monthsShown={monthsShown}
                peekNextMonth={false}
                inline
              />
            </VStack>
          </Tabs.Content>
        </Tabs.Root>
      </VStack>
    </VStack>
  );
};

export function createUsageConfig(
  title: string,
  series: any = [],
  labels: any = []
) {
  const total = formatBytes(Array.isArray(series) ? series.reduce((t, c) => (t += c), 0) : 0);
  return {
    series: series,
    options: {
      labels: labels,
      chart: {
        width: "100%",
        height: "100%",
        type: "donut",
        animations: {
          enabled: false,
        },
      },
      title: {
        text: `${title}${total}`,
        align: "center",
        style: {
          fontWeight: "var(--chakra-fontWeights-medium)",
          color: "var(--chakra-colors-gray-300)",
        },
      },
      legend: {
        position: "bottom",
        labels: {
          colors: "#CBD5E0",
          useSeriesColors: false,
        },
      },
      stroke: {
        width: 1,
        colors: undefined,
      },
      dataLabels: {
        formatter: (val, { seriesIndex, w }) => {
          return formatBytes(w.config.series[seriesIndex], 1);
        },
      },
      tooltip: {
        custom: ({ series, seriesIndex, dataPointIndex, w }) => {
          const readable = formatBytes(series[seriesIndex], 1);
          const total = Math.max(
            (series as [number]).reduce((t, c) => (t += c)),
            1
          );
          const percent =
            Math.round((series[seriesIndex] / total) * 1000) / 10 + "%";
          return `
            <div style="
                    background-color: ${w.globals.colors[seriesIndex]};
                    padding-left:12px;
                    padding-right:12px;
                    padding-top:6px;
                    padding-bottom:6px;
                    font-size:0.725rem;
                  "
            >
              ${w.config.labels[seriesIndex]}: <b>${percent}, ${readable}</b>
            </div>
          `;
        },
      },
      colors: generateDistinctColors(series.length),
    } as ApexOptions,
  };
}
