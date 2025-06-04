import {
  Button,
  Dialog,
  Text,
  Icon,
  Spinner,
} from "@chakra-ui/react";
import { FC } from "react";
import { Trans, useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNodes } from "../lib/stores/NodesContext";
import { DeleteIcon } from "./DeleteUserModal";
import { fetch } from "../lib/api/http";

export interface DeleteNodeModalOwnProps {
  deleteCallback?: () => void;
}

export const DeleteNodeModal: FC<DeleteNodeModalOwnProps> = () => {
  const { deletingNode, setDeletingNode } = useNodes();
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const onClose = () => setDeletingNode(null);

  const { mutate: deleteNodeMutation, isPending } = useMutation({
    mutationFn: (id: number) => fetch.delete(`/api/nodes/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["nodes"] });
      onClose();
    },
  });

  const handleDelete = () => {
    if (deletingNode && deletingNode.id != null) deleteNodeMutation(deletingNode.id);
  };

  return (
    <Dialog.Root
      role="alertdialog"
      open={!!deletingNode}
      onOpenChange={(d) => !d.open && onClose()}
      placement="center"
    >
      <Dialog.Backdrop className="backdrop-blur-sm bg-black/30" />
      <Dialog.Positioner>
        <Dialog.Content maxW="sm" mx="3">
          {/* Header */}
          <Dialog.Header pt={6} pb={2} justifyContent="center">
            <Icon color="red">
              <DeleteIcon />
            </Icon>
          </Dialog.Header>

          {/* Body */}
          <Dialog.Body px={6} pb={4}>
            <Text fontWeight="semibold" fontSize="lg">
              {t("deleteNode.title")}
            </Text>
            {deletingNode && (
              <Text mt={1} fontSize="sm" color="gray.600" _osDark={{ color: "gray.400" }}>
                <Trans
                  i18nKey="deleteNode.prompt"
                  values={{ name: deletingNode.name }}
                  components={{ b: <b /> }}
                />
              </Text>
            )}
          </Dialog.Body>

          {/* Footer */}
          <Dialog.Footer gap={3} px={6} pb={6} flexDir="column">
            <Button variant="outline" size="sm" w="full" onClick={onClose}>
              {t("cancel")}
            </Button>
            <Button
              size="sm"
              w="full"
              colorPalette="red"
              loading={isPending}
              onClick={handleDelete}
            >
              {isPending && <Spinner size="xs" mr={2} />}
              {t("delete")}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
};
