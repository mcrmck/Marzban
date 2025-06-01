import {
  Alert,
  AlertDescription,
  AlertIcon,
  Box,
  Button,
  Checkbox,
  Collapse,
  FormControl,
  FormLabel,
  HStack,
  IconButton,
  Input,
  Switch,
  Text,
  Textarea,
  Tooltip,
  VStack,
  useToast,
} from "@chakra-ui/react";
import {
  EyeIcon,
  EyeSlashIcon,
} from "@heroicons/react/24/outline";
import { zodResolver } from "@hookform/resolvers/zod";
import { FC, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useQuery } from "react-query";
import { NodeSchema, NodeType } from "contexts/NodesContext";
import { fetch } from "service/http";
import { generateErrorMessage } from "utils/toastHandler";

interface NodeFormProps {
  initialValues?: NodeType | null;
  onSubmit: (values: NodeType) => void;
  submitText: string;
}

export const NodeForm: FC<NodeFormProps> = ({
  initialValues,
  onSubmit,
  submitText,
}) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [showCertificate, setShowCertificate] = useState(false);
  const [showClientCert, setShowClientCert] = useState(false);
  const [showClientKey, setShowClientKey] = useState(false);

  const { data: nodeSettings } = useQuery({
    queryKey: "node-settings",
    queryFn: () =>
      fetch<{
        min_node_version: string;
        certificate: string;
      }>("/node/settings"),
  });

  const form = useForm<NodeType>({
    resolver: zodResolver(NodeSchema),
    defaultValues: initialValues || {
      name: "",
      address: "",
      port: 0,
      api_port: 0,
      usage_coefficient: 1,
      status: "connecting",
      panel_client_cert: "",
      panel_client_key: "",
    },
  });

  const handleSubmit = async (values: NodeType) => {
    try {
      await onSubmit(values);
    } catch (error) {
      generateErrorMessage(error, toast, form);
    }
  };

  function selectText(node: HTMLElement) {
    if (window.getSelection) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(node);
      selection!.removeAllRanges();
      selection!.addRange(range);
    }
  }

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)}>
      <VStack spacing={4}>
        {nodeSettings?.certificate && (
          <Alert status="info" alignItems="start">
            <AlertDescription
              display="flex"
              flexDirection="column"
              overflow="hidden"
            >
              <span>{t("nodes.connection-hint")}</span>
              <HStack justify="end" py={2}>
                <Button
                  as="a"
                  colorScheme="primary"
                  size="xs"
                  download="ssl_client_cert.pem"
                  href={URL.createObjectURL(
                    new Blob([nodeSettings.certificate], { type: "text/plain" })
                  )}
                >
                  {t("nodes.download-certificate")}
                </Button>
                <Tooltip
                  placement="top"
                  label={t(
                    !showCertificate
                      ? "nodes.show-certificate"
                      : "nodes.hide-certificate"
                  )}
                >
                  <IconButton
                    aria-label={t(
                      !showCertificate
                        ? "nodes.show-certificate"
                        : "nodes.hide-certificate"
                    )}
                    onClick={() => setShowCertificate(!showCertificate)}
                    colorScheme="whiteAlpha"
                    color="primary"
                    size="xs"
                  >
                    {!showCertificate ? (
                      <EyeIcon width="15px" />
                    ) : (
                      <EyeSlashIcon width="15px" />
                    )}
                  </IconButton>
                </Tooltip>
              </HStack>
              <Collapse in={showCertificate} animateOpacity>
                <Text
                  bg="rgba(255,255,255,.5)"
                  _dark={{
                    bg: "rgba(255,255,255,.2)",
                  }}
                  rounded="md"
                  p="2"
                  lineHeight="1.2"
                  fontSize="10px"
                  fontFamily="Courier"
                  whiteSpace="pre"
                  overflow="auto"
                  onClick={(e) => selectText(e.target as HTMLElement)}
                >
                  {nodeSettings.certificate}
                </Text>
              </Collapse>
            </AlertDescription>
          </Alert>
        )}

        <HStack w="full">
          <FormControl isInvalid={!!form.formState?.errors?.name}>
            <FormLabel>{t("nodes.nodeName")}</FormLabel>
            <Input
              {...form.register("name")}
              placeholder="Marzban-S2"
            />
          </FormControl>
          <HStack px={1}>
            <Controller
              name="status"
              control={form.control}
              render={({ field }) => (
                <Tooltip
                  placement="top"
                  label={
                    `${t("usersTable.status")}: ` +
                    (field.value !== "disabled" ? t("active") : t("disabled"))
                  }
                >
                  <Box mt="6">
                    <Switch
                      colorScheme="primary"
                      isChecked={field.value !== "disabled"}
                      onChange={(e) => {
                        field.onChange(e.target.checked ? "connecting" : "disabled");
                      }}
                    />
                  </Box>
                </Tooltip>
              )}
            />
          </HStack>
        </HStack>

        <HStack w="full">
          <FormControl isInvalid={!!form.formState?.errors?.address}>
            <FormLabel>{t("nodes.nodeAddress")}</FormLabel>
            <Input
              {...form.register("address")}
              placeholder="51.20.12.13"
            />
          </FormControl>
        </HStack>

        <HStack w="full">
          <FormControl isInvalid={!!form.formState?.errors?.port}>
            <FormLabel>{t("nodes.nodePort")}</FormLabel>
            <Input
              {...form.register("port", { valueAsNumber: true })}
              placeholder="62050"
              type="number"
            />
          </FormControl>
          <FormControl isInvalid={!!form.formState?.errors?.api_port}>
            <FormLabel>{t("nodes.nodeAPIPort")}</FormLabel>
            <Input
              {...form.register("api_port", { valueAsNumber: true })}
              placeholder="62051"
              type="number"
            />
          </FormControl>
          <FormControl isInvalid={!!form.formState?.errors?.usage_coefficient}>
            <FormLabel>{t("nodes.usageCoefficient")}</FormLabel>
            <Input
              {...form.register("usage_coefficient", { valueAsNumber: true })}
              placeholder="1"
              type="number"
            />
          </FormControl>
        </HStack>

        <FormControl isInvalid={!!form.formState?.errors?.panel_client_cert}>
          <FormLabel>{t("nodes.panelClientCert")}</FormLabel>
          <HStack>
            <Textarea
              {...form.register("panel_client_cert")}
              placeholder={t("nodes.pastePanelClientCert")}
              fontFamily="monospace"
              rows={7}
            />
            <Tooltip
              placement="top"
              label={t(
                !showClientCert
                  ? "nodes.show-certificate"
                  : "nodes.hide-certificate"
              )}
            >
              <IconButton
                aria-label={t(
                  !showClientCert
                    ? "nodes.show-certificate"
                    : "nodes.hide-certificate"
                )}
                onClick={() => setShowClientCert(!showClientCert)}
                colorScheme="whiteAlpha"
                color="primary"
                size="xs"
              >
                {!showClientCert ? (
                  <EyeIcon width="15px" />
                ) : (
                  <EyeSlashIcon width="15px" />
                )}
              </IconButton>
            </Tooltip>
          </HStack>
        </FormControl>

        <FormControl isInvalid={!!form.formState?.errors?.panel_client_key}>
          <FormLabel>{t("nodes.panelClientKey")}</FormLabel>
          <HStack>
            <Textarea
              {...form.register("panel_client_key")}
              placeholder={t("nodes.pastePanelClientKey")}
              fontFamily="monospace"
              rows={7}
            />
            <Tooltip
              placement="top"
              label={t(
                !showClientKey
                  ? "nodes.show-certificate"
                  : "nodes.hide-certificate"
              )}
            >
              <IconButton
                aria-label={t(
                  !showClientKey
                    ? "nodes.show-certificate"
                    : "nodes.hide-certificate"
                )}
                onClick={() => setShowClientKey(!showClientKey)}
                colorScheme="whiteAlpha"
                color="primary"
                size="xs"
              >
                {!showClientKey ? (
                  <EyeIcon width="15px" />
                ) : (
                  <EyeSlashIcon width="15px" />
                )}
              </IconButton>
            </Tooltip>
          </HStack>
        </FormControl>

        <Button
          type="submit"
          colorScheme="primary"
          size="sm"
          px={5}
          w="full"
          isLoading={form.formState.isSubmitting}
        >
          {submitText}
        </Button>
      </VStack>
    </form>
  );
};