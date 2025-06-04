import {
  Button,
  HStack,
  IconButton,
  Input,
  Text,
  Textarea,
  VStack,
  Tooltip,
  Collapsible,
  Field,
  Switch,
  Alert,
} from "@chakra-ui/react";
import {
  EyeIcon,
  EyeSlashIcon,
} from "@heroicons/react/24/outline";
import { zodResolver } from "@hookform/resolvers/zod";
import { FC, useState } from "react";
import { useForm, Controller, SubmitHandler } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { NodeSchema, NodeType } from "../lib/stores/NodesContext";
import { fetch } from "../lib/api/http";
import { toaster } from "@/components/ui/toaster";

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

const DownloadCertButton = ({ pem }: { pem: string }) => {
  const { t } = useTranslation();
  const blob = new Blob([pem], { type: "text/plain" });
  const url = URL.createObjectURL(blob);

  return (
    <Button
      asChild
      size="xs"
      colorPalette="primary"
      variant="solid"
    >
      {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
      <a href={url} download="ssl_client_cert.pem">
        {t("nodes.download-certificate")}
      </a>
    </Button>
  );
};

const ToggleIconButton: FC<{ label: string; shown: boolean; onToggle: () => void }> = ({ label, shown, onToggle }) => (
  <Tooltip.Root>
    <Tooltip.Trigger asChild>
      <IconButton
        aria-label={label}
        size="xs"
        variant="ghost"
        onClick={onToggle}
      >
        {shown ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
      </IconButton>
    </Tooltip.Trigger>
    <Tooltip.Positioner>
      <Tooltip.Content>{label}</Tooltip.Content>
    </Tooltip.Positioner>
  </Tooltip.Root>
);

function selectAllText(el: HTMLElement) {
  const sel = window.getSelection();
  if (!sel) return;
  const range = document.createRange();
  range.selectNodeContents(el);
  sel.removeAllRanges();
  sel.addRange(range);
}

/* -------------------------------------------------------------------------- */
/* Component                                                                  */
/* -------------------------------------------------------------------------- */

interface NodeFormProps {
  initialValues?: NodeType | null;
  onSubmit: (values: NodeType) => void | Promise<void>;
  submitText: string;
}

export const NodeForm: FC<NodeFormProps> = ({ initialValues, onSubmit, submitText }) => {
  const { t } = useTranslation();
  // const toast = createToast; // Not needed anymore
  const [showCertificate, setShowCertificate] = useState(false);
  const [showClientCert, setShowClientCert] = useState(false);
  const [showClientKey, setShowClientKey] = useState(false);

  const { data: certificateData } = useQuery({
    queryKey: ["certificate"],
    queryFn: () => fetch.get<{ certificate: string }>("/api/certificate"),
  });

  const form = useForm<NodeType>({
    resolver: zodResolver(NodeSchema) as any,
    defaultValues:
      initialValues ?? {
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

  const handleSubmit: SubmitHandler<NodeType> = async (values) => {
    try {
      await onSubmit(values);
    } catch (err: any) {
      toaster.create({
        title: t("error"),
        description: err.message || t("nodes.errorSaving"),
        type: "error",
        duration: 5000,
        closable: true,
      });
    }
  };

  return (
    <form onSubmit={form.handleSubmit(handleSubmit as any)}>
      <VStack gap={4}>
        {/* ------------------------------------------------ Certificate hint */}
        {certificateData && (
          <Alert.Root status="info" alignItems="flex-start">
            <Alert.Description display="flex" flexDirection="column" overflow="hidden">
              <span>{t("nodes.connection-hint")}</span>
              <HStack justify="flex-end" py={2} gap={2} wrap="wrap">
                <DownloadCertButton pem={certificateData.certificate} />
                <ToggleIconButton
                  label={t(showCertificate ? "nodes.hide-certificate" : "nodes.show-certificate")}
                  shown={showCertificate}
                  onToggle={() => setShowCertificate((v) => !v)}
                />
              </HStack>
              <Collapsible.Root open={showCertificate}>
                <Collapsible.Content>
                  <Text
                    bg="whiteAlpha.500"
                    _osDark={{ bg: "whiteAlpha.200" }}
                    rounded="md"
                    p={2}
                    fontSize="10px"
                    fontFamily="Courier"
                    whiteSpace="pre"
                    overflow="auto"
                    lineHeight="1.2"
                    onClick={(e) => selectAllText(e.currentTarget)}
                  >
                    {certificateData.certificate}
                  </Text>
                </Collapsible.Content>
              </Collapsible.Root>
            </Alert.Description>
          </Alert.Root>
        )}

        {/* ---------------------------------------------------------------- Name & status */}
        <HStack w="full" gap={3} wrap="wrap">
          <Field.Root invalid={!!form.formState.errors.name} flex={1} minW="200px">
            <Field.Label>{t("nodes.nodeName")}</Field.Label>
            <Input placeholder="Marzban-S2" {...form.register("name")} />
          </Field.Root>

          <Controller
            name="status"
            control={form.control}
            render={({ field }) => (
              <Switch.Root
                id="node-status-switch"
                checked={field.value !== "disabled"}
                onCheckedChange={(d) => field.onChange(d.checked ? "connecting" : "disabled")}
                aria-label={t("nodes.statusToggle")}
              >
                <Switch.Control />
              </Switch.Root>
            )}
          />
        </HStack>

        {/* ---------------------------------------------------------------- Address */}
        <Field.Root invalid={!!form.formState.errors.address} w="full">
          <Field.Label>{t("nodes.nodeAddress")}</Field.Label>
          <Input placeholder="51.20.12.13" {...form.register("address")} />
        </Field.Root>

        {/* ---------------------------------------------------------------- Ports & coeff */}
        <HStack w="full" gap={3} wrap="wrap">
          <Field.Root invalid={!!form.formState.errors.port} flex={1} minW="120px">
            <Field.Label>{t("nodes.nodePort")}</Field.Label>
            <Input type="number" placeholder="62050" {...form.register("port", { valueAsNumber: true })} />
          </Field.Root>
          <Field.Root invalid={!!form.formState.errors.api_port} flex={1} minW="120px">
            <Field.Label>{t("nodes.nodeAPIPort")}</Field.Label>
            <Input type="number" placeholder="62051" {...form.register("api_port", { valueAsNumber: true })} />
          </Field.Root>
          <Field.Root invalid={!!form.formState.errors.usage_coefficient} flex={1} minW="140px">
            <Field.Label>{t("nodes.usageCoefficient")}</Field.Label>
            <Input type="number" placeholder="1" {...form.register("usage_coefficient", { valueAsNumber: true })} />
          </Field.Root>
        </HStack>

        {/* ---------------------------------------------------------------- Client cert */}
        <Field.Root invalid={!!form.formState.errors.panel_client_cert} w="full">
          <Field.Label>{t("nodes.panelClientCert")}</Field.Label>
          <HStack align="start" gap={2} wrap="wrap">
            <Textarea
              placeholder={t("nodes.pastePanelClientCert")}
              fontFamily="monospace"
              rows={7}
              flex={1}
              {...form.register("panel_client_cert")}
            />
            <ToggleIconButton
              label={t(showClientCert ? "nodes.hide-certificate" : "nodes.show-certificate")}
              shown={showClientCert}
              onToggle={() => setShowClientCert((v) => !v)}
            />
          </HStack>
        </Field.Root>

        {/* ---------------------------------------------------------------- Client key */}
        <Field.Root invalid={!!form.formState.errors.panel_client_key} w="full">
          <Field.Label>{t("nodes.panelClientKey")}</Field.Label>
          <HStack align="start" gap={2} wrap="wrap">
            <Textarea
              placeholder={t("nodes.pastePanelClientKey")}
              fontFamily="monospace"
              rows={7}
              flex={1}
              {...form.register("panel_client_key")}
            />
            <ToggleIconButton
              label={t(showClientKey ? "nodes.hide-certificate" : "nodes.show-certificate")}
              shown={showClientKey}
              onToggle={() => setShowClientKey((v) => !v)}
            />
          </HStack>
        </Field.Root>

        {/* ---------------------------------------------------------------- Submit */}
        <Button type="submit" colorPalette="primary" loading={form.formState.isSubmitting} w="full">
          {submitText}
        </Button>
      </VStack>
    </form>
  );
};
