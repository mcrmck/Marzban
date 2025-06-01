import {
  Box,
  Button,
  HStack,
  IconButton,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  useDisclosure,
  VStack,
} from "@chakra-ui/react";
import { EditIcon, DeleteIcon } from "@chakra-ui/icons";
import { FC, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNodes, useNodesQuery, NodeType } from "contexts/NodesContext";
import { NodeModalStatusBadge } from "./NodeModalStatusBadge";
import { EditNodeDialog } from "./EditNodeDialog";
import { DeleteNodeModal } from "./DeleteNodeModal";
import { ReloadIcon } from "./Filters";

export const NodesTable: FC = () => {
  const { t } = useTranslation();
  const { data: nodes, isLoading } = useNodesQuery();
  const { setDeletingNode, reconnectNode } = useNodes();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [selectedNode, setSelectedNode] = useState<NodeType | null>(null);

  const handleEdit = (node: NodeType) => {
    setSelectedNode(node);
    onOpen();
  };

  const handleDelete = (node: NodeType) => {
    setDeletingNode(node);
  };

  const handleReconnect = (node: NodeType) => {
    reconnectNode(node);
  };

  return (
    <Box>
      <VStack spacing={4} align="stretch">
        <HStack justifyContent="flex-end">
          <Button
            colorScheme="primary"
            size="sm"
            onClick={() => {
              setSelectedNode(null);
              onOpen();
            }}
          >
            {t("nodes.addNewNode")}
          </Button>
        </HStack>

        <Table variant="simple">
          <Thead>
            <Tr>
              <Th>{t("nodes.nodeName")}</Th>
              <Th>{t("nodes.nodeAddress")}</Th>
              <Th>{t("nodes.status")}</Th>
              <Th>{t("nodes.xrayVersion")}</Th>
              <Th>{t("nodes.actions")}</Th>
            </Tr>
          </Thead>
          <Tbody>
            {nodes?.map((node) => (
              <Tr key={node.id}>
                <Td>{node.name}</Td>
                <Td>{node.address}</Td>
                <Td>
                  <NodeModalStatusBadge status={node.status || "connecting"} />
                </Td>
                <Td>{node.xray_version || "-"}</Td>
                <Td>
                  <HStack spacing={2}>
                    <IconButton
                      aria-label="edit node"
                      icon={<EditIcon />}
                      size="sm"
                      onClick={() => handleEdit(node)}
                    />
                    <IconButton
                      aria-label="delete node"
                      icon={<DeleteIcon />}
                      size="sm"
                      colorScheme="red"
                      onClick={() => handleDelete(node)}
                    />
                    {node.status === "error" && (
                      <IconButton
                        aria-label="reconnect node"
                        icon={<ReloadIcon />}
                        size="sm"
                        onClick={() => handleReconnect(node)}
                      />
                    )}
                  </HStack>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </VStack>

      <EditNodeDialog
        isOpen={isOpen}
        onClose={onClose}
        node={selectedNode}
      />
      <DeleteNodeModal />
    </Box>
  );
};