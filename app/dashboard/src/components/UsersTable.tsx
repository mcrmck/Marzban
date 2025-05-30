import {
  Accordion,
  AccordionButton,
  AccordionItem,
  AccordionPanel,
  Box,
  Button,
  chakra,
  ExpandedIndex,
  HStack,
  IconButton,
  Select,
  Slider,
  SliderFilledTrack,
  SliderProps,
  SliderTrack,
  Table,
  TableProps,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  useBreakpointValue,
  VStack,
} from "@chakra-ui/react";
import {
  CheckIcon,
  ChevronDownIcon,
  ClipboardIcon,
  LinkIcon,
  PencilIcon,
  QrCodeIcon,
} from "@heroicons/react/24/outline";
import { ReactComponent as AddFileIcon } from "assets/add_file.svg";
import classNames from "classnames";
import { resetStrategy, statusColors } from "constants/UserSettings";
import { FilterType, useDashboard } from "contexts/DashboardContext"; // Import FilterType
import { t } from "i18next";
import { FC, Fragment, useEffect, useState } from "react";
import CopyToClipboard from "react-copy-to-clipboard";
import { useTranslation } from "react-i18next";
import { User } from "types/User";
import { formatBytes } from "utils/formatByte";
import { OnlineBadge } from "./OnlineBadge";
import { OnlineStatus } from "./OnlineStatus";
import { Pagination } from "./Pagination";
import { StatusBadge } from "./StatusBadge";

const EmptySectionIcon = chakra(AddFileIcon);

const iconProps = {
  baseStyle: {
    w: {
      base: 4,
      md: 5,
    },
    h: {
      base: 4,
      md: 5,
    },
  },
};
const CopyIcon = chakra(ClipboardIcon, iconProps);
const AccordionArrowIcon = chakra(ChevronDownIcon, iconProps);
const CopiedIcon = chakra(CheckIcon, iconProps);
const SubscriptionLinkIcon = chakra(LinkIcon, iconProps);
const QRIcon = chakra(QrCodeIcon, iconProps);
const EditIcon = chakra(PencilIcon, iconProps);
const SortIcon = chakra(ChevronDownIcon, {
  baseStyle: {
    width: "15px",
    height: "15px",
  },
});
type UsageSliderProps = {
  used: number;
  total: number | null;
  dataLimitResetStrategy: string | null;
  totalUsedTraffic: number;
} & SliderProps;

const getResetStrategy = (strategy: string): string => {
  for (var i = 0; i < resetStrategy.length; i++) {
    const entry = resetStrategy[i];
    if (entry.value == strategy) {
      return entry.title;
    }
  }
  return "No";
};
const UsageSliderCompact: FC<UsageSliderProps> = (props) => {
  const { used, total } = props; // dataLimitResetStrategy, totalUsedTraffic not used
  const isUnlimited = total === 0 || total === null;
  return (
    <HStack
      justifyContent="space-between"
      fontSize="xs"
      fontWeight="medium"
      color="gray.600"
      _dark={{
        color: "gray.400",
      }}
    >
      <Text>
        {formatBytes(used)} /{" "}
        {isUnlimited ? (
          <Text as="span" fontFamily="system-ui">
            ∞
          </Text>
        ) : (
          formatBytes(total)
        )}
      </Text>
    </HStack>
  );
};
const UsageSlider: FC<UsageSliderProps> = (props) => {
  const {
    used,
    total,
    dataLimitResetStrategy,
    totalUsedTraffic,
    ...restOfProps
  } = props;
  const isUnlimited = total === 0 || total === null;
  const value = isUnlimited ? 0 : total ? Math.min((used / total) * 100, 100) : 0;
  const isReached = !isUnlimited && total !== null && used >= total;

  return (
    <>
      <Slider
        orientation="horizontal"
        value={value}
        colorScheme={isReached ? "red" : "primary"}
        {...restOfProps}
      >
        <SliderTrack h="6px" borderRadius="full">
          <SliderFilledTrack borderRadius="full" />
        </SliderTrack>
      </Slider>
      <HStack
        justifyContent="space-between"
        fontSize="xs"
        fontWeight="medium"
        color="gray.600"
        _dark={{
          color: "gray.400",
        }}
      >
        <Text>
          {formatBytes(used)} /{" "}
          {isUnlimited ? (
            <Text as="span" fontFamily="system-ui">
              ∞
            </Text>
          ) : (
            formatBytes(total) +
            (dataLimitResetStrategy && dataLimitResetStrategy !== "no_reset"
              ? " " +
                t(
                  `userDialog.resetStrategy.${dataLimitResetStrategy}`, // Corrected i18n key usage
                   getResetStrategy(dataLimitResetStrategy) // Fallback text
                )
              : "")
          )}
        </Text>
        <Text>
          {t("usersTable.total")}: {formatBytes(totalUsedTraffic)}
        </Text>
      </HStack>
    </>
  );
};
export type SortType = {
  sort: string;
  column: string;
};
export const Sort: FC<SortType> = ({ sort, column }) => {
  if (sort.includes(column))
    return (
      <SortIcon
        transform={sort.startsWith("-") ? undefined : "rotate(180deg)"}
      />
    );
  return null;
};
type UsersTableProps = {} & TableProps;
export const UsersTable: FC<UsersTableProps> = (props) => {
  const {
    filters,
    users: usersData, // Renamed to avoid conflict with users variable inside map
    onEditingUser,
    onFilterChange,
  } = useDashboard();

   // --- ADD THIS LOG ---
   console.error("UsersTable received usersData:", JSON.stringify(usersData, null, 2));
   // --- END LOG ---


  const { users, total: totalUsersCount } = usersData; // Destructure from usersData

  const { t } = useTranslation();
  const [selectedRow, setSelectedRow] = useState<ExpandedIndex | undefined>(
    undefined
  );
  const [top, setTop] = useState<string>("72px");
  const useTable = useBreakpointValue({ base: false, md: true });

  useEffect(() => {
    const calcTop = () => {
      const el = document.querySelectorAll("#filters")[0] as HTMLElement;
      if (el) {
        setTop(`${el.offsetHeight}px`);
      }
    };
    calcTop();
    window.addEventListener("resize", calcTop);
    return () => {
      window.removeEventListener("resize", calcTop);
    }
  }, []);

  const isFiltered = users.length !== totalUsersCount;

  const handleSort = (column: string) => {
    let newSort = filters.sort;
    if (newSort.includes(column)) {
      if (newSort.startsWith("-")) {
        newSort = "-created_at";
      } else {
        newSort = "-" + column;
      }
    } else {
      newSort = column;
    }
    onFilterChange({
      sort: newSort,
      offset: 0,
    });
  };

  const handleStatusFilter = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedValue = e.target.value;
    // The values from the <select> options are known to be these specific strings or an empty string.
    // These are assignable to FilterType['status'] where an empty string becomes undefined.
    const newStatusValue = selectedValue === ""
      ? undefined
      : selectedValue as FilterType['status']; // Correctly cast to the expected type

    onFilterChange({
      status: newStatusValue,
      offset: 0,
    });
  };

  const toggleAccordion = (index: number) => {
    setSelectedRow(index === selectedRow ? undefined : index);
  };

  return (
    <Box>
      {!useTable ? (
        <Accordion
          allowMultiple
          display={{ base: "block", md: "none" }}
          index={selectedRow}
        >
          <Table orientation="vertical" zIndex="docked" {...props}>
            <Thead zIndex="docked" position="relative">
              <Tr>
                <Th
                  position="sticky"
                  top={top}
                  minW="120px"
                  pl={4}
                  pr={4}
                  cursor={"pointer"}
                  onClick={handleSort.bind(null, "account_number")}
                >
                  <HStack>
                    <span>{t("accountNumber")}</span>
                    <Sort sort={filters.sort} column="account_number" />
                  </HStack>
                </Th>
                <Th
                  position="sticky"
                  top={top}
                  minW="120px" // Increased minW for clarity
                  pl={0}
                  pr={0}
                  w="140px"
                  cursor={"pointer"} // Make header clickable for sorting/filtering if desired
                >
                  <HStack spacing={0} position="relative">
                    <Text
                      position="absolute"
                      left={2} // Adjust for padding
                      top="50%"
                      transform="translateY(-50%)"
                      _dark={{
                        bg: "gray.750", // Use theme colors
                      }}
                      _light={{
                        bg: "gray.50", // Use theme colors for light mode
                      }}
                      userSelect="none"
                      pointerEvents="none"
                      zIndex={1}
                      // w="100%" // Let it size to content
                      fontSize="xs"
                      fontWeight="extrabold"
                      textTransform="uppercase"
                    >
                      {t("usersTable.status")}
                      {filters.status ? `: ${t(`status.${filters.status}`, filters.status)}` : ""}
                    </Text>
                    <Select
                      value={filters.status || ""}
                      fontSize="xs"
                      fontWeight="extrabold"
                      textTransform="uppercase"
                      cursor="pointer"
                      p={0} // Remove padding if text is hidden
                      pl={2} pr={2} // Minimal padding for the select box itself
                      border={0}
                      h="auto"
                      minH="38px" // Ensure it's clickable
                      w="100%" // Full width of Th
                      icon={<ChevronDownIcon style={{width: "16px", height: "16px", opacity: 0.7}}/>} // Visible icon
                      iconSize="sm"
                      _focusVisible={{
                        border: "0 !important",
                        boxShadow: "outline", // Add focus outline for accessibility
                      }}
                      onChange={handleStatusFilter}
                      // color="transparent" // Keep text visible for accessibility if underlying text is complex
                      // sx={{ caretColor: "transparent" }}
                    >
                      <option value="">{t("usersTable.allStatuses", "All")}</option>
                      <option value="active">{t("status.active", "Active")}</option>
                      <option value="on_hold">{t("status.on_hold", "On Hold")}</option>
                      <option value="disabled">{t("status.disabled", "Disabled")}</option>
                      <option value="limited">{t("status.limited", "Limited")}</option>
                      <option value="expired">{t("status.expired", "Expired")}</option>
                    </Select>
                  </HStack>
                </Th>
                <Th
                  position="sticky"
                  top={top}
                  minW="100px"
                  cursor={"pointer"}
                  pr={0}
                  onClick={handleSort.bind(null, "used_traffic")}
                >
                  <HStack>
                    <span>{t("usersTable.dataUsage")}</span>
                    <Sort sort={filters.sort} column="used_traffic" />
                  </HStack>
                </Th>
                <Th
                  position="sticky"
                  top={top}
                  minW="32px"
                  w="32px"
                  p={0}
                ></Th>
              </Tr>
            </Thead>
            <Tbody>
              {!useTable &&
                users?.map((user, i) => {
                  return (
                    <Fragment key={user.account_number}>
                      <Tr
                        onClick={() => toggleAccordion(i)}
                        cursor="pointer"
                      >
                        <Td
                          borderBottom={selectedRow === i ? 0 : "1px solid"} // Conditional border
                          borderColor="inherit"
                          minW="100px"
                          pl={4}
                          pr={4}
                          maxW="calc(100vw - 140px - 100px - 32px - 32px)" // Adjusted for new status column width
                        >
                          <HStack spacing={2}>
                            <OnlineBadge lastOnline={user.online_at} />
                            <Text isTruncated title={user.account_number}>{user.account_number}</Text>
                          </HStack>
                        </Td>
                        <Td borderBottom={selectedRow === i ? 0 : "1px solid"} borderColor="inherit" minW="140px" pl={0} pr={0}>
                          <StatusBadge
                            compact
                            showDetail={false}
                            expiryDate={user.expire}
                            status={user.status}
                          />
                        </Td>
                        <Td borderBottom={selectedRow === i ? 0 : "1px solid"} borderColor="inherit" minW="100px" pr={0}>
                          <UsageSliderCompact
                            totalUsedTraffic={user.lifetime_used_traffic}
                            dataLimitResetStrategy={
                              user.data_limit_reset_strategy
                            }
                            used={user.used_traffic}
                            total={user.data_limit}
                          />
                        </Td>
                        <Td p={0} borderBottom={selectedRow === i ? 0 : "1px solid"} borderColor="inherit" w="32px" minW="32px">
                          <AccordionArrowIcon
                            color="gray.600"
                            _dark={{
                              color: "gray.400",
                            }}
                            transition="transform .2s ease-out"
                            transform={
                              selectedRow === i ? "rotate(180deg)" : "rotate(0deg)"
                            }
                          />
                        </Td>
                      </Tr>
                      {selectedRow === i && (
                         <Tr className="collapsible expanded">
                           <Td p={0} colSpan={4} borderBottomWidth="1px">
                              <AccordionItem border={0} style={{display: 'block'}}>
                                  <AccordionPanel
                                    border={0}
                                    cursor="default"
                                    px={6}
                                    py={3}
                                  >
                                    <VStack justifyContent="space-between" spacing="4">
                                      <VStack
                                        alignItems="flex-start"
                                        w="full"
                                        spacing={1}
                                      >
                                        <Text
                                          textTransform="capitalize"
                                          fontSize="xs"
                                          fontWeight="bold"
                                          color="gray.600"
                                          _dark={{
                                            color: "gray.400",
                                          }}
                                        >
                                          {t("usersTable.dataUsage")}
                                        </Text>
                                        <Box width="full" minW="230px">
                                          <UsageSlider
                                            totalUsedTraffic={
                                              user.lifetime_used_traffic
                                            }
                                            dataLimitResetStrategy={
                                              user.data_limit_reset_strategy
                                            }
                                            used={user.used_traffic}
                                            total={user.data_limit}
                                            colorScheme={
                                              statusColors[user.status]?.bandWidthColor || "primary"
                                            }
                                          />
                                        </Box>
                                      </VStack>
                                      <HStack w="full" justifyContent="space-between">
                                        <Box width="full">
                                          <StatusBadge
                                            compact={false}
                                            expiryDate={user.expire}
                                            status={user.status}
                                          />
                                          <OnlineStatus lastOnline={user.online_at} />
                                        </Box>
                                        <HStack>
                                          <ActionButtons user={user} />
                                          {/* Edit button is now part of ActionButtons for mobile expanded view */}
                                        </HStack>
                                      </HStack>
                                    </VStack>
                                  </AccordionPanel>
                              </AccordionItem>
                            </Td>
                        </Tr>
                      )}
                    </Fragment>
                  );
                })}
            </Tbody>
          </Table>
        </Accordion>
      ) : (
        <Table
          variant="simple"
          display={{ base: "none", md: "table" }}
          {...props}
        >
          <Thead zIndex="docked" position="relative">
            <Tr>
              <Th
                position="sticky"
                top={{ base: "unset", md: top }}
                minW="200px"
                cursor={"pointer"}
                onClick={handleSort.bind(null, "account_number")}
              >
                <HStack>
                  <span>{t("accountNumber")}</span>
                  <Sort sort={filters.sort} column="account_number" />
                </HStack>
              </Th>
              <Th
                position="sticky"
                top={{ base: "unset", md: top }}
                width="250px"
                minW="200px" // Increased minW
              >
                <HStack position="relative" justify="space-between" w="full">
                   <HStack flexGrow={1} cursor="pointer" onClick={handleSort.bind(null, "status")}>
                      <Text userSelect="none">
                          {t("usersTable.status")}
                          {filters.status ? `: ${t(`status.${filters.status}`, filters.status)}` : ""}
                      </Text>
                      <Sort sort={filters.sort} column="status" />
                   </HStack>
                   <Text userSelect="none" px={2}>/</Text>
                   <HStack cursor="pointer" onClick={handleSort.bind(null, "expire")}>
                      <Text userSelect="none">{t("usersTable.expireDate", "Expire Date")}</Text>
                      <Sort sort={filters.sort} column="expire" />
                   </HStack>
                   <Select
                      aria-label={t("usersTable.filterByStatus", "Filter by status")}
                      value={filters.status || ""}
                      fontSize="xs"
                      fontWeight="extrabold"
                      textTransform="uppercase"
                      cursor="pointer"
                      position={"absolute"}
                      opacity={0}
                      zIndex={2}
                      top={0} left={0} w="full" h="full"
                      onChange={handleStatusFilter}
                      _focusVisible={{ outline: "none" }}
                   >
                      <option value="">{t("usersTable.allStatuses")}</option>
                      <option value="active">{t("status.active", "Active")}</option>
                      <option value="on_hold">{t("status.on_hold", "On Hold")}</option>
                      <option value="disabled">{t("status.disabled", "Disabled")}</option>
                      <option value="limited">{t("status.limited", "Limited")}</option>
                      <option value="expired">{t("status.expired", "Expired")}</option>
                   </Select>
                </HStack>
              </Th>
              <Th
                position="sticky"
                top={{ base: "unset", md: top }}
                width="350px"
                minW="230px"
                cursor={"pointer"}
                onClick={handleSort.bind(null, "used_traffic")}
              >
                <HStack>
                  <span>{t("usersTable.dataUsage")}</span>
                  <Sort sort={filters.sort} column="used_traffic" />
                </HStack>
              </Th>
              <Th
                position="sticky"
                top={{ base: "unset", md: top }}
                width="180px" // Reduced width for actions
                minW="150px" // Reduced minW
              />
            </Tr>
          </Thead>
          <Tbody>
            {useTable &&
              users?.map((user, i) => {
                return (
                  <Tr
                    key={user.account_number}
                    className={classNames("interactive", { // Ensure "interactive" class is defined
                      "last-row": i === users.length - 1,
                    })}
                    onClick={() => onEditingUser(user)}
                    cursor="pointer"
                    _hover={{bg: "gray.50", _dark: {bg: "gray.700"}}} // Hover effect
                  >
                    <Td minW="200px">
                      <HStack spacing={2}>
                          <OnlineBadge lastOnline={user.online_at} />
                          <Text isTruncated title={user.account_number}>{user.account_number}</Text>
                      </HStack>
                      <OnlineStatus lastOnline={user.online_at} />
                    </Td>
                    <Td width="250px" minW="200px">
                      <StatusBadge
                        expiryDate={user.expire}
                        status={user.status}
                        compact={false}
                      />
                    </Td>
                    <Td width="350px" minW="230px">
                      <UsageSlider
                        totalUsedTraffic={user.lifetime_used_traffic}
                        dataLimitResetStrategy={user.data_limit_reset_strategy}
                        used={user.used_traffic}
                        total={user.data_limit}
                        colorScheme={statusColors[user.status]?.bandWidthColor || "primary"}
                      />
                    </Td>
                    <Td width="180px" minW="150px">
                      <ActionButtons user={user} />
                    </Td>
                  </Tr>
                );
              })}
            {users.length === 0 && (
              <Tr>
                <Td colSpan={4}>
                  <EmptySection isFiltered={isFiltered} />
                </Td>
              </Tr>
            )}
          </Tbody>
        </Table>
      )}
      {totalUsersCount > (filters.limit || 0) && <Pagination />}
    </Box>
  );
};

type ActionButtonsProps = {
  user: User;
};

const ActionButtons: FC<ActionButtonsProps> = ({ user }) => {
  const { setQRCode, setSubLink, onEditingUser } = useDashboard();

  // --- ADD THIS LOG ---
  console.log("ActionButtons received user:", JSON.stringify(user, null, 2));
  if (user) {
    console.log("ActionButtons user.account_number:", user.account_number, "Type:", typeof user.account_number);
  }
  // --- END LOG ---

  const proxyLinks = user.links?.join("\r\n") || "";

  const [copied, setCopied] = useState<[number, boolean]>([-1, false]);
  const { t } = useTranslation();

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    if (copied[1]) {
      timeoutId = setTimeout(() => {
        setCopied([-1, false]);
      }, 1000);
    }
    return () => clearTimeout(timeoutId);
  }, [copied]);

  const handleCopy = (textToCopy: string, copyIndex: number) => {
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy)
        .then(() => setCopied([copyIndex, true]))
        .catch(err => console.error("Failed to copy text: ", err));
    }
  };


  return (
    <HStack
      spacing={{base: 1, md: 2}} // Adjust spacing
      justifyContent="flex-end"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      <Tooltip
        label={
          copied[0] === 0 && copied[1]
            ? t("usersTable.copied", "Copied!")
            : t("usersTable.copyLink", "Copy Subscription Link")
        }
        placement="top" hasArrow
      >
        <IconButton
          aria-label={t("usersTable.copyLink", "Copy Subscription Link")}
          icon={copied[0] === 0 && copied[1] ? <CopiedIcon /> : <SubscriptionLinkIcon />}
          variant="ghost" // Consistent variant
          size="sm" // Consistent size
          onClick={() => {
             const subUrl = user.subscription_url.startsWith("/")
                ? window.location.origin + user.subscription_url
                : user.subscription_url;
             handleCopy(subUrl, 0);
          }}
        />
      </Tooltip>
      <Tooltip
        label={
          copied[0] === 1 && copied[1]
            ? t("usersTable.copied", "Copied!")
            : t("usersTable.copyConfigs", "Copy All Configs")
        }
        placement="top" hasArrow
      >
        <IconButton
          aria-label={t("usersTable.copyConfigs", "Copy All Configs")}
          icon={copied[0] === 1 && copied[1] ? <CopiedIcon /> : <CopyIcon />}
          variant="ghost"
          size="sm"
          onClick={() => handleCopy(proxyLinks, 1)}
          isDisabled={!proxyLinks}
        />
      </Tooltip>
      <Tooltip label={t("usersTable.qrCode", "QR Code")} placement="top" hasArrow>
        <IconButton
          aria-label={t("usersTable.qrCode", "QR Code")}
          icon={<QRIcon />}
          variant="ghost"
          size="sm"
          onClick={() => {
            if (user.links && user.links.length > 0) setQRCode(user.links);
            setSubLink(user.subscription_url);
          }}
          isDisabled={!user.links || user.links.length === 0}
        />
      </Tooltip>
      <Tooltip label={t("userDialog.editUser", "Edit User")} placement="top" hasArrow >
        <IconButton
          aria-label={t("userDialog.editUser", "Edit User")}
          icon={<EditIcon />}
          variant="ghost"
          size="sm"
          onClick={() => onEditingUser(user)}
        />
      </Tooltip>
    </HStack>
  );
};

type EmptySectionProps = {
  isFiltered: boolean;
};

const EmptySection: FC<EmptySectionProps> = ({ isFiltered }) => {
  const { onCreateUser } = useDashboard();
  const {t} = useTranslation();
  return (
    <Box
      padding="5"
      py="8"
      display="flex"
      alignItems="center"
      flexDirection="column"
      gap={4}
      w="full"
    >
      <EmptySectionIcon
        height="150px" // Adjusted size
        width="150px"  // Adjusted size
        _dark={{
          'path[fill="#fff"]': {
            fill: "gray.800",
          },
          'path[fill="#f2f2f2"], path[fill="#e6e6e6"], path[fill="#ccc"]': {
            fill: "gray.700",
          },
          'circle[fill="#3182CE"]': {
            fill: "primary.300",
          },
        }}
        _light={{
          'path[fill="#f2f2f2"], path[fill="#e6e6e6"], path[fill="#ccc"]': {
            fill: "gray.300",
          },
          'circle[fill="#3182CE"]': {
            fill: "primary.500",
          },
        }}
      />
      <Text fontWeight="medium" color="gray.600" _dark={{ color: "gray.400" }}>
        {isFiltered ? t("usersTable.noUserMatched", "No users matched your filters.") : t("usersTable.noUser", "No users found.")}
      </Text>
      {!isFiltered && (
        <Button
          size="sm"
          colorScheme="primary"
          onClick={() => onCreateUser(true)}
          leftIcon={<AddFileIcon width="1em" height="1em"/>} // Example icon
        >
          {t("createUser", "Create User")}
        </Button>
      )}
    </Box>
  );
};