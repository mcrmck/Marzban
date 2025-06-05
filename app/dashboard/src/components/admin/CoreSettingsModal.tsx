import {
  Badge,
  Box,
  Button,
  HStack,
  IconButton,
  Dialog,
  DialogBody,
  DialogFooter,
  Text,
  Icon,
  CloseButton,
} from "@chakra-ui/react";
import {
  ArrowPathIcon,
  ArrowsPointingInIcon,
  ArrowsPointingOutIcon,
  Cog6ToothIcon,
} from "@heroicons/react/24/outline";
import classNames from "classnames";
import { useCoreSettings } from "../../lib/stores/CoreSettingsContext";
import { useDashboard } from "../../lib/stores/DashboardContext";
import debounce from "lodash.debounce";
import { FC, useCallback, useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { ReadyState } from "react-use-websocket";
import { useWebSocket } from "react-use-websocket/dist/lib/use-websocket";
import { getAuthToken } from "../../lib/utils/authStorage";
import { JsonEditor } from "./JsonEditor";
import "./JsonEditor/themes.js";
import { useNodesQuery } from "../../lib/stores/NodesContext";
import { toaster } from "../shared/ui/toaster";

export const MAX_NUMBER_OF_LOGS = 500;

const UsageIcon = Cog6ToothIcon;
const ReloadIcon = ArrowPathIcon;
const FullScreenIcon = ArrowsPointingOutIcon;
const ExitFullScreenIcon = ArrowsPointingInIcon;

const getStatus = (status: string) => {
  return {
    [ReadyState.CONNECTING]: "connecting",
    [ReadyState.OPEN]: "connected",
    [ReadyState.CLOSING]: "closed",
    [ReadyState.CLOSED]: "closed",
    [ReadyState.UNINSTANTIATED]: "closed",
  }[status];
};

const getWebsocketUrl = (nodeID: string | null) => {
  if (!nodeID) return null;

  try {
    let baseURL = new URL(
      import.meta.env.VITE_BASE_API.startsWith("/")
        ? window.location.origin + import.meta.env.VITE_BASE_API
        : import.meta.env.VITE_BASE_API
    );

    const path = `${baseURL.pathname}/node/${nodeID}/logs`.replace(/\/+/g, '/');
    return (
      (baseURL.protocol === "https:" ? "wss://" : "ws://") +
      baseURL.host + path +
      "?interval=1&token=" +
      getAuthToken()
    );
  } catch (e) {
    console.error("Unable to generate websocket url");
    console.error(e);
    return null;
  }
};

let logsTmp: string[] = [];
const CoreSettingModalContent: FC = () => {
  const { data: nodes } = useNodesQuery();
  const disabled = false;
  const [selectedNode, setNode] = useState<string | null>(null);
  const form = useForm({
    defaultValues: { config: {} },
  });

  const { isEditingCore } = useDashboard();
  const {
    fetchCoreSettings,
    updateConfig,
    isLoading,
    config,
    isPostLoading,
    version,
    restartCore,
  } = useCoreSettings();
  const logsDiv = useRef<HTMLDivElement | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const { t } = useTranslation();

  const scrollShouldStayOnEnd = useRef(true);
  const updateLogs = useCallback(
    debounce((logs: string[]) => {
      const isScrollOnEnd =
        Math.abs(
          (logsDiv.current?.scrollTop || 0) -
            (logsDiv.current?.scrollHeight || 0) +
            (logsDiv.current?.offsetHeight || 0)
        ) < 10;
      if (logsDiv.current && isScrollOnEnd)
        scrollShouldStayOnEnd.current = true;
      else scrollShouldStayOnEnd.current = false;
      if (logs.length < 40) setLogs(logs);
    }, 300),
    []
  );

  const { readyState } = useWebSocket(getWebsocketUrl(selectedNode), {
    onMessage: (e: any) => {
      logsTmp.push(e.data);
      if (logsTmp.length > MAX_NUMBER_OF_LOGS)
        logsTmp = logsTmp.splice(0, logsTmp.length - MAX_NUMBER_OF_LOGS);
      updateLogs([...logsTmp]);
    },
    shouldReconnect: () => true,
    reconnectAttempts: 10,
    reconnectInterval: 1000,
  });

  useEffect(() => {
    if (logsDiv.current && scrollShouldStayOnEnd.current)
      logsDiv.current.scrollTop = logsDiv.current?.scrollHeight;
  }, [logs]);

  useEffect(() => {
    return () => {
      logsTmp = [];
    };
  }, []);

  const status = getStatus(readyState.toString());

  const { mutate: handleRestartCore, isPending: isRestarting } =
    useMutation({
      mutationFn: restartCore
    });

  const handleLog = (id: string, title: string) => {
    if (id === selectedNode) return;
    setNode(id);
    setLogs([]);
    logsTmp = [];
  };

  const handleOnSave = ({ config }: any) => {
    updateConfig(config)
      .then(() => {
        toaster.create({
          title: t("core.successMessage"),
          type: "success",
          duration: 3000,
        });
      })
      .catch((e) => {
        let message = t("core.generalErrorMessage");
        if (typeof e.response._data.detail === "object")
          message =
            e.response._data.detail[Object.keys(e.response._data.detail)[0]];
        if (typeof e.response._data.detail === "string")
          message = e.response._data.detail;

        toaster.create({
          title: message,
          type: "error",
          duration: 3000,
        });
      });
  };
  const editorRef = useRef<HTMLDivElement>(null);
  const [isFullScreen, setFullScreen] = useState(false);
  const handleFullScreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen();
      setFullScreen(false);
    } else {
      editorRef.current?.requestFullscreen();
      setFullScreen(true);
    }
  };

  useEffect(() => {
    if (config) form.setValue("config", config);
  }, [config]);

  useEffect(() => {
    if (isEditingCore) fetchCoreSettings();
  }, [isEditingCore]);

  return (
    <form onSubmit={form.handleSubmit(handleOnSave)}>
      <DialogBody>
        <Box>
          <HStack justifyContent="space-between" alignItems="flex-start">
            <Text as="label">
              {t("core.configuration")}{" "}
              {isLoading && <Box as="span" display="inline-block" w="15px" h="15px" border="2px solid" borderColor="currentColor" borderRadius="full" borderTopColor="transparent" animation="spin 1s linear infinite" />}
            </Text>
            <HStack gap={0}>
              <Box as="div" role="tooltip" aria-label="Panel Version">
                <Badge height="100%" textTransform="lowercase">
                  {version && `v${version}`}
                </Badge>
              </Box>
            </HStack>
          </HStack>
          <Box position="relative" ref={editorRef} minHeight="300px">
            <Controller
              control={form.control}
              name="config"
              render={({ field }) => (
                <JsonEditor json={config} onChange={field.onChange} />
              )}
            />
            <IconButton
              size="xs"
              aria-label="full screen"
              variant="ghost"
              position="absolute"
              top="2"
              right="4"
              onClick={handleFullScreen}
            >
              {!isFullScreen ? <FullScreenIcon width={16} height={16} /> : <ExitFullScreenIcon width={12} height={12} />}
            </IconButton>
          </Box>
        </Box>
        <Box mt="4">
          <HStack
            justifyContent="space-between"
            style={{ paddingBottom: "1rem" }}
          >
            <HStack>
              {nodes?.[0] && (
                <select
                  style={{
                    width: "auto",
                    backgroundColor: disabled ? "var(--chakra-colors-gray-100)" : "transparent",
                    padding: "0.5rem",
                    borderRadius: "0.375rem",
                    border: "1px solid var(--chakra-colors-gray-200)"
                  }}
                  disabled={disabled}
                  onChange={(e) =>
                    handleLog(
                      e.currentTarget.value,
                      e.currentTarget.selectedOptions[0].text
                    )
                  }
                >
                  <option value="">Select a node to view logs</option>
                  {nodes &&
                    nodes.map((s) => {
                      return (
                        <option key={s.address} value={String(s.id)}>
                          {t(s.name)}
                        </option>
                      );
                    })}
                </select>
              )}
              <Text as="label" className="w-au">{t("core.logs")}</Text>
            </HStack>
            <Text as="label">{t(`core.socket.${status}`)}</Text>
          </HStack>
          <Box
            border="1px solid"
            borderColor="gray.300"
            bg="#F9F9F9"
            _dark={{
              borderColor: "gray.500",
              bg: "#2e3440",
            }}
            borderRadius={5}
            minHeight="200px"
            maxHeight={"250px"}
            p={2}
            overflowY="auto"
            ref={logsDiv}
          >
            {logs.map((message, i) => (
              <Text fontSize="xs" opacity={0.8} key={i} whiteSpace="pre-line">
                {message}
              </Text>
            ))}
          </Box>
        </Box>
      </DialogBody>
      <DialogFooter>
        <HStack w="full" justifyContent="space-between">
          <HStack>
            <Box>
              <Button
                size="sm"
                onClick={() => handleRestartCore()}
              >
                <ReloadIcon
                  width={16}
                  height={16}
                  className={classNames({
                    "animate-spin": isRestarting,
                  })}
                />
                {t(isRestarting ? "core.restarting" : "core.restartCore")}
              </Button>
            </Box>
          </HStack>

          <HStack>
            <Button
              size="sm"
              variant="solid"
              colorPalette="primary"
              px="5"
              type="submit"
              disabled={isLoading || isPostLoading}
              loading={isPostLoading}
            >
              {t("core.save")}
            </Button>
          </HStack>
        </HStack>
      </DialogFooter>
    </form>
  );
};
export const CoreSettingsModal: FC = () => {
  const { isEditingCore } = useDashboard();
  const onClose = () => useDashboard.setState({ isEditingCore: false } as any);
  const { t } = useTranslation();

  return (
    <Dialog.Root open={isEditingCore} onOpenChange={(details) => details.open || onClose()}>
      <Dialog.Backdrop bg="blackAlpha.300" backdropFilter="blur(10px)" />
      <Dialog.Content mx="3" w="full">
        <Dialog.Header pt={6}>
          <HStack gap={2}>
            <Icon color="primary">
              <UsageIcon width={20} height={20} color="white" />
            </Icon>
            <Text fontWeight="semibold" fontSize="lg">
              {t("core.title")}
            </Text>
          </HStack>
        </Dialog.Header>
        <CloseButton position="absolute" right="8px" top="8px" onClick={onClose} />
        <CoreSettingModalContent />
      </Dialog.Content>
    </Dialog.Root>
  );
};
