import {
  Button,
  chakra,
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
import { TrashIcon } from "@heroicons/react/24/outline";
import { useDashboard } from "contexts/DashboardContext";
import { FC, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import { User } from "types/User"; // Added import

export const DeleteIcon = chakra(TrashIcon, {
  baseStyle: {
    w: 5,
    h: 5,
  },
});

export type DeleteUserModalProps = {
  isOpen: boolean;
  onClose: () => void;
  user: User;
  deleteCallback?: () => void;
};

export const DeleteUserModal: FC<DeleteUserModalProps> = ({ isOpen, onClose, user }) => {
  const { t } = useTranslation();
  const { deleteUser } = useDashboard();
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteUser(user); // Changed from user.account_number to user
      onClose();
    } catch (error) {
      console.error(error);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{t("deleteUser")}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Text>
            {/* Using user.account_number for display is fine */}
            <Trans i18nKey="deleteUserConfirm" values={{ account_number: user.account_number }}>
              Are you sure you want to delete user {{ account_number: user.account_number }}? This action cannot be undone.
            </Trans>
          </Text>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button
            colorScheme="red"
            onClick={handleDelete}
            isLoading={isDeleting}
          >
            {t("delete")}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};