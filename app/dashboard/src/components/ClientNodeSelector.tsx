/* ClientNodeSelector.tsx — Chakra UI v3 */

import React, { useEffect, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Field,
  Heading,
  HStack,
  Spinner,
  useClipboard,
  VStack,
  Select,
  createListCollection,
} from "@chakra-ui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { fetcher } from "../lib/api/http";
import {
  activateNodeForClient,
  ClientNodeActivationResponse,
  getClientActiveNode,
} from "../lib/api/clientNodeService";
import { Node } from "../lib/types/node";
import {
  NodeServiceConfigurationResponse,
} from "../lib/types/NodeService";
import { toaster } from "@/components/ui/toaster";

/* -------------------------------------------------------------------------- */
/* Types                                                                      */
/* -------------------------------------------------------------------------- */

interface ApiResponse<T> {
  data: { data: T };
}

interface ClientNodeSelectorProps {
  accountNumber: string;
}

/* -------------------------------------------------------------------------- */
/* Component                                                                  */
/* -------------------------------------------------------------------------- */

export const ClientNodeSelector: React.FC<ClientNodeSelectorProps> = ({
  accountNumber,
}) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  /* local state */
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedService, setSelectedService] =
    useState<NodeServiceConfigurationResponse | null>(null);
  const [connectionString, setConnectionString] = useState("");
  const { copy } = useClipboard({ value: connectionString });

  /* ---------------------------------------------------------------------- */
  /* Queries                                                                */
  /* ---------------------------------------------------------------------- */

  /* all nodes */
  const { data: nodes, isLoading: isLoadingNodes } = useQuery<Node[]>({
    queryKey: ["nodes"],
    queryFn: () =>
      fetcher
        .get<ApiResponse<Node[]>>("/api/nodes")
        .then((res) => res.data.data),
  });

  /* client's active node */
  const { data: activeNode } = useQuery<{
    node_id: number;
    service: NodeServiceConfigurationResponse;
  }>({
    queryKey: ["client-active-node", accountNumber],
    queryFn: () => getClientActiveNode(accountNumber),
    enabled: !!accountNumber,
  });

  /* services for current node */
  const { data: services, isLoading: isLoadingServices } = useQuery<
    NodeServiceConfigurationResponse[]
  >({
    queryKey: ["node-services", selectedNode?.id],
    queryFn: () =>
      selectedNode
        ? fetcher
            .get<ApiResponse<NodeServiceConfigurationResponse[]>>(
              `/nodes/${selectedNode.id}/services/`,
            )
            .then((res) => res.data.data)
        : Promise.resolve([]),
    enabled: !!selectedNode,
  });

  /* ---------------------------------------------------------------------- */
  /* Effects                                                                 */
  /* ---------------------------------------------------------------------- */

  /* initialise selections from server "active-node" */
  useEffect(() => {
    if (activeNode && nodes) {
      const n = nodes.find((x) => x.id === activeNode.node_id) ?? null;
      setSelectedNode(n);
      setSelectedService(activeNode.service ?? null);
    }
  }, [activeNode, nodes]);

  /* ---------------------------------------------------------------------- */
  /* Handlers                                                                */
  /* ---------------------------------------------------------------------- */

  const handleNodeChange = (id: string) => {
    const n = nodes?.find((x) => x.id.toString() === id) ?? null;
    setSelectedNode(n);
    setSelectedService(null);
  };

  const handleServiceChange = (id: string) => {
    const s = services?.find((x) => x.id.toString() === id) ?? null;
    setSelectedService(s);
  };

  const activationMutation = useMutation<
    ClientNodeActivationResponse,
    unknown,
    void
  >({
    mutationFn: () =>
      activateNodeForClient(
        accountNumber,
        selectedNode!.id,
        selectedService!.id,
      ),
  });

  const doActivate = async () => {
    try {
      const res = await activationMutation.mutateAsync();
      queryClient.invalidateQueries({
        queryKey: ["client-active-node", accountNumber],
      });
      setConnectionString(res.connection_string);
      copy();
      toaster.create({
        title: t("clientNodeSelector.activationSuccess"),
        description: t("clientNodeSelector.activationSuccessDesc"),
        type: "success",
        duration: 5000,
        closable: true,
      });
    } catch (err: any) {
      toaster.create({
        title: t("clientNodeSelector.activationError"),
        description: err?.message ?? "Unknown error",
        type: "error",
        duration: 5000,
        closable: true,
      });
    }
  };

  /* ---------------------------------------------------------------------- */
  /* Collections for Select components                                      */
  /* ---------------------------------------------------------------------- */

  const nodesCollection = createListCollection({
    items:
      nodes?.map((n) => ({
        id: n.id.toString(),
        label: `${n.name} (${n.address})`,
      })) ?? [],
  });

  const servicesCollection = createListCollection({
    items:
      services?.map((s) => ({
        id: s.id.toString(),
        label: `${s.service_name} (${s.protocol_type})`,
      })) ?? [],
  });

  /* ---------------------------------------------------------------------- */
  /* Render                                                                  */
  /* ---------------------------------------------------------------------- */

  if (isLoadingNodes) {
    return (
      <Box textAlign="center" py={10}>
        <Spinner size="xl" />
      </Box>
    );
  }

  return (
    <Box borderWidth="1px" borderRadius="lg" p={6}>
      <VStack gap={6} align="stretch">
        {/* Node select ---------------------------------------------------- */}
        <Box>
          <Heading size="md" mb={4}>
            {t("clientNodeSelector.title")}
          </Heading>

          <Field.Root>
            <Field.Label>{t("clientNodeSelector.selectNode")}</Field.Label>

            <Select.Root
              collection={nodesCollection}
              value={selectedNode ? [selectedNode.id.toString()] : []}
              onValueChange={(d: { value: string[] }) =>
                handleNodeChange(d.value[0])
              }
            >
              <Select.Trigger borderRadius="6px">
                <Select.ValueText
                  placeholder={t("clientNodeSelector.selectNodePlaceholder")}
                />
              </Select.Trigger>
              <Select.Positioner>
                <Select.Content>
                  {nodesCollection.items.map((item) => (
                    <Select.Item key={item.id} item={item}>
                      {item.label}
                    </Select.Item>
                  ))}
                </Select.Content>
              </Select.Positioner>
            </Select.Root>
          </Field.Root>
        </Box>

        {/* Service select -------------------------------------------------- */}
        {selectedNode && (
          <Box>
            <Field.Root>
              <Field.Label>{t("clientNodeSelector.selectService")}</Field.Label>

              <Select.Root
                collection={servicesCollection}
                disabled={isLoadingServices}
                value={selectedService ? [selectedService.id.toString()] : []}
                onValueChange={(d: { value: string[] }) =>
                  handleServiceChange(d.value[0])
                }
              >
                <Select.Trigger borderRadius="6px">
                  <Select.ValueText
                    placeholder={t(
                      "clientNodeSelector.selectServicePlaceholder",
                    )}
                  />
                </Select.Trigger>
                <Select.Positioner>
                  <Select.Content>
                    {servicesCollection.items.map((item) => (
                      <Select.Item key={item.id} item={item}>
                        {item.label}
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Positioner>
              </Select.Root>
            </Field.Root>
          </Box>
        )}

        {/* Service badges -------------------------------------------------- */}
        {selectedService && (
          <HStack gap={4}>
            <Badge colorPalette="green">{selectedService.protocol_type}</Badge>
            {selectedService.network_type && (
              <Badge colorPalette="blue">{selectedService.network_type}</Badge>
            )}
            {selectedService.security_type !== "none" && (
              <Badge colorPalette="purple">
                {selectedService.security_type}
              </Badge>
            )}
          </HStack>
        )}

        {/* Activate button ------------------------------------------------- */}
        <Button
          colorPalette="blue"
          onClick={doActivate}
          disabled={!selectedNode || !selectedService}
          loading={activationMutation.isPending}
        >
          {t("clientNodeSelector.activate")}
        </Button>
      </VStack>
    </Box>
  );
};
