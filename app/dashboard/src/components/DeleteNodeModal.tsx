import {
  Button,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Spinner,
  Text,
  useToast,
} from "@chakra-ui/react";
import { FetchNodesQueryKey, NodeType, useNodes } from "contexts/NodesContext"; // Added NodeType
import { FC } from "react";
import { Trans, useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "react-query";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "utils/toastHandler";
import { DeleteIcon } from "./DeleteUserModal";
import { Icon } from "./Icon";

export type DeleteNodeModalOwnProps = {
  deleteCallback?: () => void;
};

export const DeleteNodeModal: FC<DeleteNodeModalOwnProps> = ({
  deleteCallback,
}) => {
  const { deleteNode, deletingNode, setDeletingNode } = useNodes();
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const onClose = () => {
    setDeletingNode(null);
  };

  const { isLoading, mutate: onDelete } = useMutation<unknown, Error, NodeType>(
    deleteNode,
    {
      onSuccess: () => {
        generateSuccessMessage(
          t("deleteNode.deleteSuccess", { name: deletingNode?.name || "" }),
          toast
        );
        setDeletingNode(null);
        queryClient.invalidateQueries(FetchNodesQueryKey);
        if (deleteCallback) {
          deleteCallback();
        }
      },
      onError: (e) => {
        generateErrorMessage(e, toast);
      },
    }
  );

  const handleDelete = () => {
    if (deletingNode) {
      onDelete(deletingNode);
    }
  };

  return (
    <Modal isCentered isOpen={!!deletingNode} onClose={onClose} size="sm">
      <ModalOverlay bg="blackAlpha.300" backdropFilter="blur(10px)" />
      <ModalContent mx="3">
        <ModalHeader pt={6}>
          <Icon color="red">
            <DeleteIcon />
          </Icon>
        </ModalHeader>
        <ModalCloseButton mt={3} />
        <ModalBody>
          <Text fontWeight="semibold" fontSize="lg">
            {t("deleteNode.title")}
          </Text>
          {deletingNode && (
            <Text
              mt={1}
              fontSize="sm"
              _dark={{ color: "gray.400" }}
              color="gray.600"
            >
              <Trans
              i18nKey="deleteNode.prompt"
              values={{ name: deletingNode?.name ?? "" }}
              components={{ b: <b /> }}
            >
              Are you sure you want to delete node <b>{deletingNode.name}</b>?
            </Trans>
            </Text>
          )}
        </ModalBody>
        <ModalFooter display="flex">
          <Button size="sm" onClick={onClose} mr={3} w="full" variant="outline">
            {t("cancel")}
          </Button>
          <Button
            size="sm"
            w="full"
            colorScheme="red"
            onClick={handleDelete}
            leftIcon={isLoading ? <Spinner size="xs" /> : undefined}
            disabled={isLoading || !deletingNode}
          >
            {t("delete")}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};