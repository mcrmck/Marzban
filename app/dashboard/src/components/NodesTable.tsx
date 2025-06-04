/* --------------------------------------------------------------------
 * NodesTable.tsx – Chakra UI v3 compliant
 * ------------------------------------------------------------------ */

import {
  Box,
  Button,
  HStack,
  IconButton,
  Table,
  VStack,
  useDisclosure,
} from "@chakra-ui/react";
import {
  PencilIcon as HeroEditIcon,
  TrashIcon as HeroDeleteIcon,
} from "@heroicons/react/24/outline";
import { FC, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNodes, useNodesQuery, NodeType } from "../lib/stores/NodesContext";
import { NodeModalStatusBadge } from "./NodeModalStatusBadge";
import { EditNodeDialog } from "./EditNodeDialog";
import { DeleteNodeModal } from "./DeleteNodeModal";
import { ReloadIcon } from "./Filters";

export const NodesTable: FC = () => {
  const { t } = useTranslation();
  const { data: nodes } = useNodesQuery();
  const { setDeletingNode, reconnectNode } = useNodes();

  const { open, onOpen, onClose } = useDisclosure();
  const [selectedNode, setSelectedNode] = useState<NodeType | null>(null);

  const handleEdit = (node: NodeType) => {
    setSelectedNode(node);
    onOpen();
  };

  const handleDelete = (node: NodeType) => setDeletingNode(node);

  const handleReconnect = (node: NodeType) => reconnectNode(node);

  return (
    <Box>
      <VStack gap={4} align="stretch">
        {/* ── Add-node button ─────────────────────────────────────────── */}
        <HStack justify="flex-end">
          <Button
            size="sm"
            colorPalette="primary"
            onClick={() => {
              setSelectedNode(null);
              onOpen();
            }}
          >
            {t("nodes.addNewNode")}
          </Button>
        </HStack>

        {/* ── Nodes table ─────────────────────────────────────────────── */}
        <Table.Root variant="line" size="sm" striped stickyHeader>
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>{t("nodes.nodeName")}</Table.ColumnHeader>
              <Table.ColumnHeader>{t("nodes.nodeAddress")}</Table.ColumnHeader>
              <Table.ColumnHeader>{t("nodes.status")}</Table.ColumnHeader>
              <Table.ColumnHeader>{t("nodes.xrayVersion")}</Table.ColumnHeader>
              <Table.ColumnHeader>{t("nodes.actions")}</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>

          <Table.Body>
            {nodes?.map((node) => (
              <Table.Row key={node.id}>
                <Table.Cell>{node.name}</Table.Cell>
                <Table.Cell>{node.address}</Table.Cell>
                <Table.Cell>
                  <NodeModalStatusBadge status={node.status || "connecting"} />
                </Table.Cell>
                <Table.Cell>{node.xray_version || "-"}</Table.Cell>
                <Table.Cell>
                  <HStack gap={1}>
                    {/* Edit */}
                    <IconButton
                      aria-label={t("edit")}
                      size="sm"
                      onClick={() => handleEdit(node)}
                    >
                      <HeroEditIcon className="h-4 w-4" />
                    </IconButton>

                    {/* Delete */}
                    <IconButton
                      aria-label={t("delete")}
                      size="sm"
                      colorPalette="red"
                      onClick={() => handleDelete(node)}
                    >
                      <HeroDeleteIcon className="h-4 w-4" />
                    </IconButton>

                    {/* Re-connect (only on error) */}
                    {node.status === "error" && (
                      <IconButton
                        aria-label={t("nodes.reconnect")}
                        size="sm"
                        onClick={() => handleReconnect(node)}
                      >
                        <ReloadIcon />
                      </IconButton>
                    )}
                  </HStack>
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      </VStack>

      {/* ── Dialogs ──────────────────────────────────────────────────── */}
      <EditNodeDialog open={open} onClose={onClose} node={selectedNode} />
      <DeleteNodeModal />
    </Box>
  );
};
