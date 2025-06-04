/* UserDialog.tsx — Chakra UI v3 */

import {
  Alert,
  Box,
  Button,
  CheckboxGroup,
  Collapsible,
  createListCollection,
  Dialog,
  Field,
  Flex,
  Grid,
  GridItem,
  HStack,
  Icon,
  IconButton,
  Input,
  InputAddon,
  InputGroup,
  Portal,
  Select,
  Switch,
  Text,
  Textarea,
  Tooltip,
  VStack,
  Checkbox,
  Select as ChakraSelect,
} from "@chakra-ui/react";
import { useTheme } from "next-themes";
import { toaster } from "@/components/ui/toaster";

import {
  ArrowPathIcon as HeroArrowPathIcon,
  ChartPieIcon as HeroChartPieIcon,
  PencilIcon as HeroPencilIcon,
  UserPlusIcon as HeroUserPlusIcon,
} from "@heroicons/react/24/outline";

import { zodResolver } from "@hookform/resolvers/zod";
import { FilterUsageType, useDashboard } from "../lib/stores/DashboardContext";
import dayjs from "dayjs";
import { FC, useEffect, useState } from "react";
import ReactApexChart from "react-apexcharts";
import ReactDatePicker from "react-datepicker";
import {
  Controller,
  FormProvider,
  SubmitHandler,
  useForm,
  useWatch,
} from "react-hook-form";
import { useTranslation } from "react-i18next";
import type { ProxyType, User, UserCreate, UserInbounds } from "../lib/types/User";
import { relativeExpiryDate } from "../lib/utils/dateFormatter";
import { z } from "zod";
import { DeleteIcon } from "./DeleteUserModal";
import { UsageFilter, createUsageConfig } from "./UsageFilter";

/* ────────────────────────────────────────────────────────────────────────── */
/* Enums & helpers                                                           */
/* ────────────────────────────────────────────────────────────────────────── */

const UserStatus = {
  ACTIVE: "active",
  DISABLED: "disabled",
  LIMITED: "limited",
  EXPIRED: "expired",
  ON_HOLD: "on_hold",
} as const;
type UserStatusValues = (typeof UserStatus)[keyof typeof UserStatus];

const DataLimitResetStrategy = {
  NO_RESET: "no_reset",
  DAY: "day",
  WEEK: "week",
  MONTH: "month",
} as const;
type DataLimitResetStrategyValues =
  (typeof DataLimitResetStrategy)[keyof typeof DataLimitResetStrategy];

const PROXY_KEYS = [
  { title: "vless", description: "VLESS Protocol" },
  { title: "vmess", description: "VMess Protocol" },
  { title: "trojan", description: "Trojan Protocol" },
  { title: "shadowsocks", description: "Shadowsocks Protocol" },
] as const;
type ProxyKeys = (typeof PROXY_KEYS)[number]["title"];

export interface FormType {
  account_number: string;
  proxies: {
    vless: { id: string; flow: string };
    vmess: { id: string };
    trojan: { password: string };
    shadowsocks: { password: string; method: string };
  };
  expire: number | null;
  data_limit: number;
  data_limit_reset_strategy: DataLimitResetStrategyValues;
  on_hold_expire_duration: number | null;
  status: UserStatusValues;
  note: string | null;
  inbounds: UserInbounds;
  selected_proxies: string[];
}

/* ────────────────────────────────────────────────────────────────────────── */
/* Utility functions                                                         */
/* ────────────────────────────────────────────────────────────────────────── */

const convertInboundsMapToRecord = (
  m?: Map<string, { tag: string }[]>,
): Record<string, { tag: string }[]> | undefined => {
  if (!m) return undefined;
  const r: Record<string, { tag: string }[]> = {};
  m.forEach((v, k) => {
    r[k] = v.map(({ tag }) => ({ tag }));
  });
  return r;
};

const getDefaultValues = (
  inbounds?: Record<string, { tag: string }[]>,
): FormType => {
  const defaultUserInbounds: UserInbounds = {};
  if (inbounds) {
    Object.keys(inbounds).forEach((k) => {
      defaultUserInbounds[k] = inbounds[k].map((i) => i.tag);
    });
  }
  return {
    selected_proxies: [],
    data_limit: 0,
    expire: null,
    account_number: "",
    data_limit_reset_strategy: DataLimitResetStrategy.NO_RESET,
    status: UserStatus.ACTIVE,
    on_hold_expire_duration: null,
    note: "",
    inbounds: defaultUserInbounds,
    proxies: {
      vless: { id: "", flow: "" },
      vmess: { id: "" },
      trojan: { password: "" },
      shadowsocks: { password: "", method: "chacha20-ietf-poly1305" },
    },
  };
};

const formatUserToForm = (u: User): FormType => ({
  ...u,
  status: u.status as UserStatusValues,
  data_limit_reset_strategy:
    u.data_limit_reset_strategy as DataLimitResetStrategyValues,
  data_limit: u.data_limit
    ? parseFloat((u.data_limit / 1_073_741_824).toFixed(5))
    : 0,
  on_hold_expire_duration: u.on_hold_expire_duration
    ? u.on_hold_expire_duration / 86_400
    : 0,
  selected_proxies: Object.keys(u.proxies ?? {}),
  proxies: {
    vless: { id: u.proxies?.vless?.id ?? "", flow: u.proxies?.vless?.flow ?? "" },
    vmess: { id: u.proxies?.vmess?.id ?? "" },
    trojan: { password: u.proxies?.trojan?.password ?? "" },
    shadowsocks: {
      password: u.proxies?.shadowsocks?.password ?? "",
      method: u.proxies?.shadowsocks?.method ?? "chacha20-ietf-poly1305",
    },
  },
  inbounds: u.inbounds ?? {},
  note: u.note ?? null,
});

const mergeProxies = (
  keys: string[],
  proxies?: ProxyType,
): ProxyType => {
  const p: ProxyType = {};
  keys.forEach((k) => {
    if (!PROXY_KEYS.find(({ title }) => title === k)) return;
    switch (k as ProxyKeys) {
      case "vless":
        p.vless = { id: "", flow: "" };
        break;
      case "vmess":
        p.vmess = { id: "" };
        break;
      case "trojan":
        p.trojan = { password: "" };
        break;
      case "shadowsocks":
        p.shadowsocks = { password: "", method: "chacha20-ietf-poly1305" };
        break;
    }
  });
  if (proxies) {
    keys.forEach((k) => {
      if ((proxies as any)[k]) (p as any)[k] = (proxies as any)[k];
    });
  }
  return p;
};

/* ────────────────────────────────────────────────────────────────────────── */
/* Validation schema                                                         */
/* ────────────────────────────────────────────────────────────────────────── */

const schema = z.object({
  account_number: z.string().min(1, "Required"),
  selected_proxies: z.array(z.string()),
  note: z.string().nullable(),
  proxies: z.object({
    vless: z.object({ id: z.string(), flow: z.string() }),
    vmess: z.object({ id: z.string() }),
    trojan: z.object({ password: z.string() }),
    shadowsocks: z.object({ password: z.string(), method: z.string() }),
  }),
  data_limit: z
    .preprocess(
      (v) => (v === "" || v == null ? null : Number(v)),
      z.number().positive("Must be positive").nullable(),
    )
    .transform((v) => (v != null ? Math.round(v * 1_073_741_824) : 0)),
  expire: z.number().nullable(),
  data_limit_reset_strategy: z.nativeEnum(DataLimitResetStrategy),
  inbounds: z.record(z.string(), z.array(z.string())),
  status: z.nativeEnum(UserStatus),
  on_hold_expire_duration: z
    .preprocess(
      (v) => (v === "" || v == null ? null : Number(v)),
      z.number().min(0.1, "Required").nullable(),
    )
    .transform((v) => (v != null ? Math.round(v * 86_400) : null)),
}) as z.ZodType<FormType>;

/* ────────────────────────────────────────────────────────────────────────── */
/* Component                                                                 */
/* ────────────────────────────────────────────────────────────────────────── */

export const UserDialog: FC = () => {
  const {
    editingUser,
    isCreatingNewUser,
    onCreateUser,
    editUser,
    fetchUserUsage,
    onEditingUser,
    createUser,
    onDeletingUser,
    inbounds: allInbounds,
  } = useDashboard();

  const { t, i18n } = useTranslation();
  const { theme: colorMode } = useTheme();

  const isEditing = Boolean(editingUser);
  const isOpen = isCreatingNewUser || isEditing;

  const form = useForm<FormType>({
    defaultValues: getDefaultValues(convertInboundsMapToRecord(allInbounds)),
    resolver: zodResolver(schema),
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* watch GB + status for conditional fields */
  const [formDataLimitGB, userFormStatus] = useWatch({
    control: form.control,
    name: ["data_limit", "status"],
  });

  const isOnHold = userFormStatus === UserStatus.ON_HOLD;

  /* usage chart state */
  const usageTitle = t("userDialog.total");
  const [usage, setUsage] = useState(
    createUsageConfig(colorMode ?? "light", usageTitle, [[], []]),
  );
  const [usageVisible, setUsageVisible] = useState(false);
  const [usageFilter, setUsageFilter] = useState("1m");

  const fetchUsageWithFilter = (query: FilterUsageType) => {
    if (!editingUser) return;
    fetchUserUsage(editingUser, query)
      .then((d: any) => {
        const labels = d.usages ? Object.keys(d.usages) : [];
        const series = d.usages
          ? Object.values(d.usages).map((u: any) => u.used_traffic)
          : [];
        setUsage(
          createUsageConfig(colorMode ?? "light", usageTitle, [series, labels]),
        );
      })
      .catch(console.error);
  };

  /* sync form when editing / inbounds change */
  useEffect(() => {
    if (editingUser) {
      form.reset(formatUserToForm(editingUser));
      fetchUsageWithFilter({
        start: dayjs().utc().subtract(30, "day").format("YYYY-MM-DDTHH:00:00Z"),
      });
    } else {
      form.reset(getDefaultValues(convertInboundsMapToRecord(allInbounds)));
    }
  }, [editingUser, allInbounds]);

  const randomUsername = () =>
    form.setValue("account_number", crypto.randomUUID());

  const onSubmit: SubmitHandler<FormType> = (values) => {
    setLoading(true);
    setError(null);

    const { selected_proxies, ...rest } = values;
    const body: UserCreate = {
      ...rest,
      proxies: mergeProxies(selected_proxies, values.proxies),
      data_limit_reset_strategy:
        values.data_limit && values.data_limit > 0
          ? values.data_limit_reset_strategy
          : DataLimitResetStrategy.NO_RESET,
      note: values.note ?? "",
    };

    const api = isEditing ? editUser(body) : createUser(body);
    api
      .then(() =>
        toaster.create({
          title: t(
            isEditing ? "userDialog.userEdited" : "userDialog.userCreated",
            { username: values.account_number },
          ),
          type: "success",
          duration: 3000,
        }),
      )
      .then(closeDialog)
      .catch((err: any) => {
        const detail =
          err?.response?._data?.detail ?? err?.message ?? "Unknown error";
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        if (err?.response?.status === 422 && typeof detail === "object") {
          Object.keys(detail).forEach((k) =>
            form.setError(k as any, { type: "custom", message: detail[k] }),
          );
        }
      })
      .finally(() => setLoading(false));
  };

  const closeDialog = () => {
    form.reset(getDefaultValues(convertInboundsMapToRecord(allInbounds)));
    setError(null);
    setUsageVisible(false);
    setUsageFilter("1m");
    onCreateUser(false);
    onEditingUser(null);
  };

  /* reset-strategy collection */
  const resetStrategyItems = [
    { label: t("userDialog.resetStrategy.noReset"), value: DataLimitResetStrategy.NO_RESET },
    { label: t("userDialog.resetStrategy.day"), value: DataLimitResetStrategy.DAY },
    { label: t("userDialog.resetStrategy.week"), value: DataLimitResetStrategy.WEEK },
    { label: t("userDialog.resetStrategy.month"), value: DataLimitResetStrategy.MONTH },
  ];
  const resetStrategyCollection = createListCollection({
    items: resetStrategyItems,
  });

  /* ──────────────────────────────────────────────────────────────────────── */
  /* JSX                                                                     */
  /* ──────────────────────────────────────────────────────────────────────── */

  return (
    <Dialog.Root open={isOpen} onOpenChange={(d) => !d.open && closeDialog()}>
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            {/* Header */}
            <Box pt={6} px={6}>
              <HStack gap={2}>
                <Icon color="primary">
                  {isEditing ? (
                    <HeroPencilIcon className="w-5 h-5" />
                  ) : (
                    <HeroUserPlusIcon className="w-5 h-5" />
                  )}
                </Icon>
                <Dialog.Title asChild>
                  <Text fontWeight="semibold" fontSize="lg">
                    {isEditing ? t("userDialog.editUserTitle") : t("createNewUser")}
                  </Text>
                </Dialog.Title>
                <Box flex="1" />
                <Dialog.CloseTrigger asChild>
                  <IconButton
                    aria-label={t("close")}
                    size="sm"
                    variant="ghost"
                    disabled={loading}
                  >
                    <DeleteIcon />
                  </IconButton>
                </Dialog.CloseTrigger>
              </HStack>
            </Box>

            {/* Body */}
            <Box px={6} py={4}>
              <FormProvider {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)}>
                  <Grid
                    templateColumns={{ base: "1fr", md: "repeat(2,1fr)" }}
                    gap={3}
                  >
                    {/* Left */}
                    <GridItem>
                      <VStack gap={3} align="stretch">
                        {/* account number + status */}
                        <Flex gap={3} wrap="wrap">
                          <Field.Root flex="1">
                            <Field.Label>{t("accountNumber")}</Field.Label>
                            <HStack>
                              <Input
                                {...form.register("account_number")}
                                size="sm"
                                borderRadius="6px"
                                disabled={loading || isEditing}
                              />
                              {!isEditing && (
                                <IconButton
                                  size="xs"
                                  variant="ghost"
                                  aria-label={t("random")}
                                  onClick={randomUsername}
                                  disabled={loading}
                                >
                                  <HeroArrowPathIcon className="h-4 w-4" />
                                </IconButton>
                              )}
                            </HStack>
                            <Field.ErrorText>
                              {form.formState.errors.account_number?.message}
                            </Field.ErrorText>
                          </Field.Root>

                          {!isEditing ? (
                            <Field.Root>
                              <Field.Label whiteSpace="nowrap">
                                {t("userDialog.onHold")}
                              </Field.Label>
                              <Controller
                                name="status"
                                control={form.control}
                                render={({ field }) => (
                                  <Switch.Root
                                    checked={field.value === UserStatus.ON_HOLD}
                                    onCheckedChange={(c) =>
                                      field.onChange(
                                        c ? UserStatus.ON_HOLD : UserStatus.ACTIVE,
                                      )
                                    }
                                    disabled={loading}
                                  >
                                    <Switch.Indicator />
                                  </Switch.Root>
                                )}
                              />
                            </Field.Root>
                          ) : (
                            <Field.Root>
                              <Field.Label mr="2">
                                {t("status.active")}
                              </Field.Label>
                              <Controller
                                name="status"
                                control={form.control}
                                render={({ field }) => (
                                  <Switch.Root
                                    checked={field.value === UserStatus.ACTIVE}
                                    onCheckedChange={(c) =>
                                      field.onChange(
                                        c ? UserStatus.ACTIVE : UserStatus.DISABLED,
                                      )
                                    }
                                    disabled={loading}
                                  >
                                    <Switch.Indicator />
                                  </Switch.Root>
                                )}
                              />
                            </Field.Root>
                          )}
                        </Flex>

                        {/* data-limit */}
                        <Field.Root>
                          <Field.Label>{t("userDialog.dataLimit")}</Field.Label>
                          <Controller
                            name="data_limit"
                            control={form.control}
                            render={({ field }) => (
                              <InputGroup endAddon="GB">
                                <Input
                                  {...field}
                                  type="number"
                                  size="sm"
                                  borderRadius="6px"
                                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                    field.onChange(
                                      e.target.value === "" ? null : Number(e.target.value),
                                    )
                                  }
                                  value={
                                    field.value == null || field.value === 0
                                      ? ""
                                      : String(field.value)
                                  }
                                  disabled={loading}
                                />
                              </InputGroup>
                            )}
                          />
                          <Field.ErrorText>
                            {form.formState.errors.data_limit?.message}
                          </Field.ErrorText>
                        </Field.Root>

                        {/* periodic reset */}
                        <Collapsible.Root
                          open={typeof formDataLimitGB === "number" && formDataLimitGB > 0}
                        >
                          <Collapsible.Content>
                            <Field.Root>
                              <Field.Label>
                                {t("userDialog.periodicUsageReset")}
                              </Field.Label>
                              <Controller
                                name="data_limit_reset_strategy"
                                control={form.control}
                                render={({ field }) => (
                                  <Select.Root
                                    collection={resetStrategyCollection}
                                    value={field.value ? [field.value] : []}
                                    onValueChange={(d) => field.onChange(d.value[0])}
                                    disabled={loading}
                                  >
                                    <Select.Trigger borderRadius="6px">
                                      <Select.ValueText
                                        placeholder={t("userDialog.selectResetStrategy")}
                                      />
                                    </Select.Trigger>
                                    <Select.Positioner>
                                      <Select.Content>
                                        {resetStrategyItems.map((item) => (
                                          <Select.Item key={item.value} item={item}>
                                            {item.label}
                                          </Select.Item>
                                        ))}
                                      </Select.Content>
                                    </Select.Positioner>
                                  </Select.Root>
                                )}
                              />
                            </Field.Root>
                          </Collapsible.Content>
                        </Collapsible.Root>

                        {/* expiry / on-hold */}
                        <Field.Root>
                          <Field.Label>
                            {isOnHold
                              ? t("userDialog.onHoldExpireDuration")
                              : t("userDialog.expiryDate")}
                          </Field.Label>

                          {isOnHold ? (
                            <Controller
                              name="on_hold_expire_duration"
                              control={form.control}
                              render={({ field }) => (
                                <InputGroup endAddon="Days">
                                  <Input
                                    {...field}
                                    type="number"
                                    size="sm"
                                    borderRadius="6px"
                                    disabled={loading}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                      field.onChange(
                                        e.target.value === "" ? null : Number(e.target.value),
                                      )
                                    }
                                    value={field.value == null ? "" : String(field.value)}
                                  />
                                </InputGroup>
                              )}
                            />
                          ) : (
                            <Controller
                              name="expire"
                              control={form.control}
                              render={({ field }) => {
                                const { status, time } = relativeExpiryDate(field.value);
                                return (
                                  <>
                                    <ReactDatePicker
                                      selected={
                                        field.value ? dayjs.unix(field.value).toDate() : null
                                      }
                                      onChange={(d) =>
                                        field.onChange(
                                          d ? dayjs(d).endOf("day").unix() : null,
                                        )
                                      }
                                      minDate={new Date()}
                                      locale={i18n.language.toLowerCase()}
                                      dateFormat={t("dateFormat") as string}
                                      customInput={
                                        <Input
                                          size="sm"
                                          borderRadius="6px"
                                          disabled={loading}
                                        />
                                      }
                                    />
                                    {field.value && (
                                      <Field.HelperText>
                                        {t(status, { time })}
                                      </Field.HelperText>
                                    )}
                                  </>
                                );
                              }}
                            />
                          )}
                          <Field.ErrorText>
                            {form.formState.errors.on_hold_expire_duration?.message ||
                              form.formState.errors.expire?.message}
                          </Field.ErrorText>
                        </Field.Root>

                        {/* note */}
                        <Field.Root>
                          <Field.Label>{t("userDialog.note")}</Field.Label>
                          <Textarea
                            {...form.register("note")}
                            size="sm"
                            borderRadius="6px"
                            disabled={loading}
                          />
                          <Field.ErrorText>
                            {form.formState.errors.note?.message}
                          </Field.ErrorText>
                        </Field.Root>

                        {error && (
                          <Alert.Root status="error" borderRadius="md">
                            <Alert.Description>{error}</Alert.Description>
                          </Alert.Root>
                        )}
                      </VStack>
                    </GridItem>

                    {/* Right: protocol checkboxes */}
                    <GridItem>
                      <Field.Root>
                        <Field.Label>{t("userDialog.protocols")}</Field.Label>
                        <Controller
                          name="selected_proxies"
                          control={form.control}
                          render={({ field }) => (
                            <CheckboxGroup
                              value={field.value}
                              onValueChange={field.onChange}
                              disabled={loading}
                            >
                              {PROXY_KEYS.map((p) => (
                                <Checkbox.Root key={p.title} value={p.title}>
                                  <Checkbox.HiddenInput />
                                  <Checkbox.Control />
                                  <Checkbox.Label>{p.description}</Checkbox.Label>
                                </Checkbox.Root>
                              ))}
                            </CheckboxGroup>
                          )}
                        />
                        <Field.ErrorText>
                          {form.formState.errors.selected_proxies?.message}
                        </Field.ErrorText>
                      </Field.Root>
                    </GridItem>

                    {/* usage chart */}
                    {isEditing && usageVisible && (
                      <GridItem colSpan={2} pt={6}>
                        <VStack gap={4}>
                          <UsageFilter
                            defaultValue={usageFilter}
                            onChange={(f, q) => {
                              setUsageFilter(f);
                              fetchUsageWithFilter(q);
                            }}
                          />
                          <Box w={{ base: "100%", md: "70%" }} mx="auto">
                            <ReactApexChart
                              options={usage.options}
                              series={usage.series}
                              type="donut"
                            />
                          </Box>
                        </VStack>
                      </GridItem>
                    )}
                  </Grid>

                  {/* Mobile error duplicate */}
                  {error && (
                    <Alert.Root
                      mt="3"
                      status="error"
                      display={{ base: "flex", md: "none" }}
                      borderRadius="md"
                    >
                      <Alert.Description>{error}</Alert.Description>
                    </Alert.Root>
                  )}

                  {/* Footer */}
                  <Box mt="4">
                    <HStack
                      justify="space-between"
                      flexDir={{ base: "column", sm: "row" }}
                      gap={3}
                    >
                      {/* left actions */}
                      {isEditing && (
                        <HStack gap={2}>
                          <Tooltip.Root>
                            <Tooltip.Trigger asChild>
                              <IconButton
                                aria-label={t("delete")}
                                size="sm"
                                onClick={() => {
                                  onDeletingUser(editingUser!);
                                  closeDialog();
                                }}
                                disabled={loading}
                              >
                                <DeleteIcon />
                              </IconButton>
                            </Tooltip.Trigger>
                            <Tooltip.Positioner>
                              <Tooltip.Content>{t("delete")}</Tooltip.Content>
                            </Tooltip.Positioner>
                          </Tooltip.Root>

                          <Tooltip.Root>
                            <Tooltip.Trigger asChild>
                              <IconButton
                                aria-label={t("userDialog.usage")}
                                size="sm"
                                onClick={() => setUsageVisible((v) => !v)}
                                disabled={loading}
                              >
                                <HeroChartPieIcon className="h-5 w-5" />
                              </IconButton>
                            </Tooltip.Trigger>
                            <Tooltip.Positioner>
                              <Tooltip.Content>
                                {t("userDialog.usage")}
                              </Tooltip.Content>
                            </Tooltip.Positioner>
                          </Tooltip.Root>

                          <Button
                            size="sm"
                            onClick={() =>
                              useDashboard.setState({ resetUsageUser: editingUser })
                            }
                            disabled={loading}
                          >
                            {t("userDialog.resetUsage")}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() =>
                              useDashboard.setState({ revokeSubscriptionUser: editingUser })
                            }
                            disabled={loading}
                          >
                            {t("userDialog.revokeSubscription")}
                          </Button>
                        </HStack>
                      )}

                      {/* submit */}
                      <Button
                        type="submit"
                        size="sm"
                        px="8"
                        colorPalette="primary"
                        loading={loading}
                        disabled={loading}
                      >
                        {isEditing ? t("userDialog.editUser") : t("createUser")}
                      </Button>
                    </HStack>
                  </Box>
                </form>
              </FormProvider>
            </Box>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
};
