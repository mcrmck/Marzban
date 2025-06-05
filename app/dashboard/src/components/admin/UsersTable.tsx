import {
  Accordion,
  Box,
  Button,
  chakra,
  HStack,
  IconButton,
  Slider,
  Table,
  Text,
  useBreakpointValue,
  VStack,
  // Removed: AccordionItem, AccordionPanel, ExpandedIndex, SliderProps, SliderTrack,
  // Removed: TableProps, Tbody, Td, Th, Thead, Tr
} from "@chakra-ui/react";
import {
  CheckIcon as HeroCheckIcon, // Renamed to avoid conflict if any
  ChevronDownIcon as HeroChevronDownIcon,
  ClipboardIcon as HeroClipboardIcon,
  LinkIcon as HeroLinkIcon,
  PencilIcon as HeroPencilIcon,
  QrCodeIcon as HeroQrCodeIcon,
} from "@heroicons/react/24/outline";

// Ensure your SVGR setup (e.g., vite-plugin-svgr with ?react suffix or CRA's default)
// provides AddFileIconSvg as a ReactComponent.
import AddFileIconSvg from "assets/add_file.svg";
import classNames from "classnames";
import { resetStrategy, statusColors } from "constants/UserSettings"; // Assuming this file is also updated for Chakra v3 if needed
import { FilterType, useDashboard } from "../../lib/stores/DashboardContext";
import { t } from "i18next"; // For the t function outside of hook
import { FC, Fragment, useEffect, useState, ComponentProps } from "react";
import { useTranslation } from "react-i18next";
import { User } from "../../lib/types/User";
import { formatBytes } from "../../lib/utils/formatByte";
import { OnlineBadge } from "../shared/OnlineBadge";
import { OnlineStatus } from "../shared/OnlineStatus";
import  Pagination  from "./Pagination";
import { StatusBadge } from "../shared/StatusBadge";


const CopyIcon = chakra(HeroClipboardIcon);
const AccordionArrowIcon = chakra(HeroChevronDownIcon);
const CopiedIcon = chakra(HeroCheckIcon);
const SubscriptionLinkIcon = chakra(HeroLinkIcon);
const QRIcon = chakra(HeroQrCodeIcon);
const EditIcon = chakra(HeroPencilIcon);
const SortIconElement = chakra(HeroChevronDownIcon);

type UsageSliderProps = {
  used: number;
  total: number | null;
  dataLimitResetStrategy: string | null;
  totalUsedTraffic: number;
} & ComponentProps<typeof Slider.Root>;

const getResetStrategyText = (strategyValue: string): string => {
  const foundStrategy = resetStrategy.find(s => s.value === strategyValue);
  return foundStrategy ? t(foundStrategy.title) : t("No");
};

const UsageSliderCompact: FC<UsageSliderProps> = (props) => {
  const { used, total } = props;
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
          formatBytes(total as number) // Cast as total here is not null
        )}
      </Text>
    </HStack>
  );
};

const UsageSlider: FC<UsageSliderProps> = ({
  used,
  total,
  dataLimitResetStrategy,
  totalUsedTraffic,
  colorScheme,
  ...restOfProps
}) => {
  const { t: translate } = useTranslation();
  const isUnlimited = total === 0 || total === null;
  const valuePercentage = isUnlimited || !total ? 0 : Math.min((used / total) * 100, 100);
  const isReached = !isUnlimited && total !== null && used >= total;

  return (
    <>
      <Slider.Root
        value={[valuePercentage]}
        colorScheme={isReached ? "red" : colorScheme || "primary"}
        {...restOfProps} // Spread remaining Slider.Root compatible props
      >
        <Slider.Track h="6px" borderRadius="full">
          <Slider.Range borderRadius="full" />
        </Slider.Track>
        <Slider.Thumb index={0} />
      </Slider.Root>
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
            formatBytes(total as number) + // Cast total as it's checked not null
            (dataLimitResetStrategy && dataLimitResetStrategy !== "no_reset"
              ? " " +
                translate(
                  `userDialog.resetStrategy.${dataLimitResetStrategy}`,
                  getResetStrategyText(dataLimitResetStrategy)
                )
              : "")
          )}
        </Text>
        <Text>
          {translate("usersTable.total")}: {formatBytes(totalUsedTraffic)}
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
      <SortIconElement
        w={4}
        h={4}
        strokeWidth={2}
        transform={sort.startsWith("-") ? undefined : "rotate(180deg)"}
      />
    );
  return null;
};

// Use ComponentProps for Table.Root if specific TableRootProps isn't directly available or known
type UsersTableProps = {} & ComponentProps<typeof Table.Root>;

export const UsersTable: FC<UsersTableProps> = (props) => {
  const {
    filters,
    users: usersData,
    onEditingUser,
    onFilterChange,
  } = useDashboard();

  console.error("UsersTable received usersData:", JSON.stringify(usersData, null, 2));

  const { users, total: totalUsersCount } = usersData;
  const { t: translate } = useTranslation();
  const [selectedRow, setSelectedRow] = useState<string | undefined>(undefined); // Accordion value is string
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
    };
  }, []);

  const isFiltered = users.length !== totalUsersCount;

  const handleSort = (column: string) => {
    let newSort = filters.sort;
    if (newSort.includes(column)) {
      newSort = newSort.startsWith("-") ? column : `-${column}`; // Simpler toggle
    } else {
      newSort = column;
    }
     if (newSort === column && filters.sort === column) { // If clicking same column and it's already sorted ascending
      newSort = `-${column}`;
    } else if (newSort === `-${column}` && filters.sort === `-${column}`) { // If clicking same column and it's already sorted descending
       newSort = "-created_at"; // Default sort or clear sort for this column
    } else if (!filters.sort.includes(column)) { // New column
        newSort = column;
    }


    onFilterChange({
      sort: newSort,
      offset: 0,
    });
  };

  const handleStatusFilterChange = (details: { value: string[] }) => {
    const selectedValue = details.value.length > 0 ? details.value[0] : "";
    const newStatusValue = selectedValue === ""
      ? undefined
      : selectedValue as FilterType['status'];

    onFilterChange({
      status: newStatusValue,
      offset: 0,
    });
  };

  const currentAccordionValue = selectedRow !== undefined ? [selectedRow] : [];

  return (
    <Box>
      {!useTable ? (
        <Accordion.Root
          collapsible
          value={currentAccordionValue}
          onValueChange={(details) => {
            setSelectedRow(details.value.length > 0 ? details.value[0] : undefined);
          }}
          display={{ base: "block", md: "none" }}
        >
          <Table.Root zIndex="docked" {...props}>
            <Table.Header zIndex="docked" position="relative">
              <Table.Row>
                <Table.ColumnHeader
                  position="sticky"
                  top={top}
                  minW="120px"
                  pl={4}
                  pr={4}
                  cursor="pointer"
                  onClick={() => handleSort("account_number")}
                >
                  <HStack gap={1}> {/* Changed spacing to gap */}
                    <span>{translate("accountNumber")}</span>
                    <Sort sort={filters.sort} column="account_number" />
                  </HStack>
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  position="sticky"
                  top={top}
                  minW="140px"
                  pl={0}
                  pr={0}
                  w="140px"
                >
                  <HStack gap={0} position="relative"> {/* Changed spacing to gap */}
                    <Text
                      position="absolute"
                      left={2}
                      top="50%"
                      transform="translateY(-50%)"
                      _dark={{ bg: "gray.750" }}
                      _light={{ bg: "gray.50" }}
                      userSelect="none"
                      pointerEvents="none"
                      zIndex={1}
                      fontSize="xs"
                      fontWeight="extrabold"
                      textTransform="uppercase"
                    >
                      {translate("usersTable.status")}
                      {filters.status ? `: ${translate(`status.${filters.status}`, filters.status as string)}` : ""}
                    </Text>
                    <select
                      value={filters.status || ""}
                      onChange={e => handleStatusFilterChange({ value: [e.target.value] })}
                      style={{ width: '100%', fontSize: '0.875rem', padding: '0.5rem' }}
                    >
                      <option value="">{translate("usersTable.allStatuses", "All")}</option>
                      <option value="active">{translate("status.active", "Active")}</option>
                      <option value="on_hold">{translate("status.on_hold", "On Hold")}</option>
                      <option value="disabled">{translate("status.disabled", "Disabled")}</option>
                      <option value="limited">{translate("status.limited", "Limited")}</option>
                      <option value="expired">{translate("status.expired", "Expired")}</option>
                    </select>
                  </HStack>
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  position="sticky"
                  top={top}
                  minW="100px"
                  cursor="pointer"
                  pr={0}
                  onClick={() => handleSort("used_traffic")}
                >
                  <HStack gap={1}> {/* Changed spacing to gap */}
                    <span>{translate("usersTable.dataUsage")}</span>
                    <Sort sort={filters.sort} column="used_traffic" />
                  </HStack>
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  position="sticky"
                  top={top}
                  minW="32px"
                  w="32px"
                  p={0}
                />
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {users?.map((user, i) => {
                const userIndexStr = i.toString();
                return (
                  <Fragment key={user.account_number}>
                    <Accordion.Item value={userIndexStr} border="none"> {/* Accordion.Item wraps rows */}
                      <Table.Row
                        onClick={() => setSelectedRow(selectedRow === userIndexStr ? undefined : userIndexStr)}
                        cursor="pointer"
                      >
                        <Table.Cell
                          borderBottom={selectedRow === userIndexStr ? 0 : "1px solid"}
                          borderColor="inherit"
                          minW="100px"
                          pl={4}
                          pr={4}
                          maxW="calc(100vw - 140px - 100px - 32px - 32px)"
                        >
                           <Accordion.ItemTrigger asChild>
                            <HStack gap={2} width="100%"> {/* Changed spacing to gap */}
                              <OnlineBadge lastOnline={user.online_at} />
                              <Text style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={user.account_number}>{user.account_number}</Text>
                            </HStack>
                          </Accordion.ItemTrigger>
                        </Table.Cell>
                        <Table.Cell borderBottom={selectedRow === userIndexStr ? 0 : "1px solid"} borderColor="inherit" minW="140px" pl={0} pr={0}>
                          <StatusBadge
                            compact
                            showDetail={false}
                            expiryDate={user.expire}
                            status={user.status}
                          />
                        </Table.Cell>
                        <Table.Cell borderBottom={selectedRow === userIndexStr ? 0 : "1px solid"} borderColor="inherit" minW="100px" pr={0}>
                          <UsageSliderCompact
                            totalUsedTraffic={user.lifetime_used_traffic}
                            dataLimitResetStrategy={user.data_limit_reset_strategy}
                            used={user.used_traffic}
                            total={user.data_limit}
                          />
                        </Table.Cell>
                        <Table.Cell p={0} borderBottom={selectedRow === userIndexStr ? 0 : "1px solid"} borderColor="inherit" w="32px" minW="32px">
                           <Accordion.ItemTrigger asChild>
                              <AccordionArrowIcon
                                color="gray.600"
                                _dark={{ color: "gray.400" }}
                                transition="transform .2s ease-out"
                                transform={selectedRow === userIndexStr ? "rotate(180deg)" : "rotate(0deg)"}
                              />
                           </Accordion.ItemTrigger>
                        </Table.Cell>
                      </Table.Row>
                       <Accordion.ItemContent> {/* Panel content */}
                        {selectedRow === userIndexStr && ( // Still need this conditional rendering for the row itself
                           <Table.Row className="collapsible expanded">
                            <Table.Cell p={0} colSpan={4} borderBottomWidth="1px">
                                <Box px={6} py={3} cursor="default"> {/* Replaced AccordionPanel direct use */}
                                  <VStack gap={4} justifyContent="space-between"> {/* Changed spacing to gap */}
                                    <VStack gap={1} alignItems="flex-start" w="full"> {/* Changed spacing to gap */}
                                      <Text
                                        textTransform="capitalize"
                                        fontSize="xs"
                                        fontWeight="bold"
                                        color="gray.600"
                                        _dark={{ color: "gray.400" }}
                                      >
                                        {translate("usersTable.dataUsage")}
                                      </Text>
                                      <Box width="full" minW="230px">
                                        <UsageSlider
                                          totalUsedTraffic={user.lifetime_used_traffic}
                                          dataLimitResetStrategy={user.data_limit_reset_strategy}
                                          used={user.used_traffic}
                                          total={user.data_limit}
                                          colorScheme={statusColors[user.status]?.bandWidthColor || "primary"}
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
                                      </HStack>
                                    </HStack>
                                  </VStack>
                                </Box>
                            </Table.Cell>
                          </Table.Row>
                        )}
                      </Accordion.ItemContent>
                    </Accordion.Item>
                  </Fragment>
                );
              })}
            </Table.Body>
          </Table.Root>
        </Accordion.Root>
      ) : (
        <Table.Root display={{ base: "none", md: "table" }} {...props}>
          <Table.Header zIndex="docked" position="relative">
            <Table.Row>
              <Table.ColumnHeader
                position="sticky"
                top={{ base: "unset", md: top }}
                minW="200px"
                cursor="pointer"
                onClick={() => handleSort("account_number")}
              >
                <HStack gap={1}> {/* Changed spacing to gap */}
                  <span>{translate("accountNumber")}</span>
                  <Sort sort={filters.sort} column="account_number" />
                </HStack>
              </Table.ColumnHeader>
              <Table.ColumnHeader
                position="sticky"
                top={{ base: "unset", md: top }}
                width="250px"
                minW="200px"
              >
                <Box>
                  <HStack justify="space-between" w="full" mb={1}>
                    <HStack cursor="pointer" onClick={() => handleSort("status")} gap={1}>
                      <Text userSelect="none" fontWeight="medium">
                        {translate("status")}
                        {filters.status ? `: ${translate(`status.${filters.status}`, filters.status as string)}` : ""}
                      </Text>
                      <Sort sort={filters.sort} column="status" />
                    </HStack>
                    <Text userSelect="none" px={1}>/</Text>
                    <HStack cursor="pointer" onClick={() => handleSort("expire")} gap={1}>
                      <Text userSelect="none" fontWeight="medium">{translate("usersTable.expireDate", "Expire Date")}</Text>
                      <Sort sort={filters.sort} column="expire" />
                    </HStack>
                  </HStack>
                  <select
                    value={filters.status || ""}
                    onChange={e => handleStatusFilterChange({ value: [e.target.value] })}
                    style={{
                      width: '100%',
                      fontSize: '0.875rem',
                      padding: '0.5rem',
                      borderRadius: '0.375rem',
                      border: '1px solid var(--chakra-colors-gray-200)',
                      backgroundColor: 'var(--chakra-colors-white)'
                    }}
                  >
                    <option value="">{translate("usersTable.allStatuses", "All")}</option>
                    <option value="active">{translate("status.active", "Active")}</option>
                    <option value="on_hold">{translate("status.on_hold", "On Hold")}</option>
                    <option value="disabled">{translate("status.disabled", "Disabled")}</option>
                    <option value="limited">{translate("status.limited", "Limited")}</option>
                    <option value="expired">{translate("status.expired", "Expired")}</option>
                  </select>
                </Box>
              </Table.ColumnHeader>
              <Table.ColumnHeader
                position="sticky"
                top={{ base: "unset", md: top }}
                width="350px"
                minW="230px"
                cursor="pointer"
                onClick={() => handleSort("used_traffic")}
                pl={4}
              >
                <HStack gap={1}>
                  <span>{translate("usersTable.dataUsage")}</span>
                  <Sort sort={filters.sort} column="used_traffic" />
                </HStack>
              </Table.ColumnHeader>
              <Table.ColumnHeader
                position="sticky"
                top={{ base: "unset", md: top }}
                width="180px"
                minW="150px"
              />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {users?.map((user, i) => (
              <Table.Row
                key={user.account_number}
                className={classNames("interactive", { "last-row": i === users.length - 1 })}
                onClick={() => onEditingUser(user)}
                cursor="pointer"
                _hover={{ bg: "gray.50", _dark: { bg: "gray.700" } }}
              >
                <Table.Cell minW="200px">
                  <HStack gap={2}> {/* Changed spacing to gap */}
                      <OnlineBadge lastOnline={user.online_at} />
                      <Text style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={user.account_number}>{user.account_number}</Text>
                  </HStack>
                  <OnlineStatus lastOnline={user.online_at} />
                </Table.Cell>
                <Table.Cell width="250px" minW="200px">
                  <StatusBadge
                    expiryDate={user.expire}
                    status={user.status}
                    compact={false}
                  />
                </Table.Cell>
                <Table.Cell width="350px" minW="230px">
                  <UsageSlider
                    totalUsedTraffic={user.lifetime_used_traffic}
                    dataLimitResetStrategy={user.data_limit_reset_strategy}
                    used={user.used_traffic}
                    total={user.data_limit}
                    colorScheme={statusColors[user.status]?.bandWidthColor || "primary"}
                  />
                </Table.Cell>
                <Table.Cell width="180px" minW="150px">
                  <ActionButtons user={user} />
                </Table.Cell>
              </Table.Row>
            ))}
            {users.length === 0 && (
              <Table.Row>
                <Table.Cell colSpan={4}>
                  <EmptySection isFiltered={isFiltered} />
                </Table.Cell>
              </Table.Row>
            )}
          </Table.Body>
        </Table.Root>
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
  const proxyLinks = user.links?.join("\r\n") || "";
  const [copied, setCopied] = useState<[number, boolean]>([-1, false]);
  const { t: translate } = useTranslation();

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
      gap={{ base: 1, md: 2 }} // Use gap
      justifyContent="flex-end"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      <IconButton
        aria-label={translate("usersTable.copyLink", "Copy Subscription Link")}
        variant="ghost"
        size="sm"
        onClick={() => {
          const subUrl = user.subscription_url.startsWith("/")
            ? window.location.origin + user.subscription_url
            : user.subscription_url;
          handleCopy(subUrl, 0);
        }}
        title={copied[0] === 0 && copied[1] ? translate("usersTable.copied", "Copied!") : translate("usersTable.copyLink", "Copy Subscription Link")}
      >
        {copied[0] === 0 && copied[1] ? <CopiedIcon /> : <SubscriptionLinkIcon />}
      </IconButton>
      <IconButton
        aria-label={translate("usersTable.copyConfigs", "Copy All Configs")}
        variant="ghost"
        size="sm"
        onClick={() => handleCopy(proxyLinks, 1)}
        disabled={!proxyLinks} // Changed from isDisabled
      >
        {copied[0] === 1 && copied[1] ? <CopiedIcon /> : <CopyIcon />}
      </IconButton>
      <IconButton
        aria-label={translate("usersTable.qrCode", "QR Code")}
        variant="ghost"
        size="sm"
        onClick={() => {
          if (user.links && user.links.length > 0) setQRCode(user.links);
          setSubLink(user.subscription_url);
        }}
        disabled={!user.links || user.links.length === 0} // Changed from isDisabled
      >
        <QRIcon />
      </IconButton>
      <IconButton
        aria-label={translate("userDialog.editUser", "Edit User")}
        variant="ghost"
        size="sm"
        onClick={() => onEditingUser(user)}
      >
        <EditIcon />
      </IconButton>
    </HStack>
  );
};

type EmptySectionProps = {
  isFiltered: boolean;
};

const EmptySection: FC<EmptySectionProps> = ({ isFiltered }) => {
  const { onCreateUser } = useDashboard();
  const { t: translate } = useTranslation();
  return (
    <Box
      padding="5"
      py="8"
      display="flex"
      alignItems="center"
      flexDirection="column"
      gap={4} // Use gap
      w="full"
    >
      <img
        src={AddFileIconSvg}
        alt="Empty section"
        height="150"
        width="150"
        style={{ display: 'block' }}
      />
      <Text fontWeight="medium" color="gray.600" _dark={{ color: "gray.400" }}>
        {isFiltered ? translate("usersTable.noUserMatched", "No users matched your filters.") : translate("usersTable.noUser", "No users found.")}
      </Text>
      {!isFiltered && (
        <Button
          size="sm"
          colorScheme="primary"
          onClick={() => onCreateUser(true)}
        >
          <img src={AddFileIconSvg} alt="" style={{ width: '1em', height: '1em', marginRight: 4, display: 'inline-block', verticalAlign: 'middle' }} />
          {translate("createUser", "Create User")}
        </Button>
      )}
    </Box>
  );
};