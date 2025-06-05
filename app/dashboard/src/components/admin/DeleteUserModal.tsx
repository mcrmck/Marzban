import {
  Button,
  Dialog,
  chakra,
} from "@chakra-ui/react";
import { TrashIcon } from "@heroicons/react/24/outline";
import { FC, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { useDashboard } from "../../lib/stores/DashboardContext";
import { User } from "../../lib/types/User";

// simple, style later via props
export const DeleteIcon = chakra(TrashIcon);

type DeleteUserModalProps = {
  open: boolean;          // v3 prop name
  onClose: () => void;
  user: User;
};

export const DeleteUserModal: FC<DeleteUserModalProps> = ({
  open,
  onClose,
  user,
}) => {
  const { t } = useTranslation();
  const { deleteUser } = useDashboard();
  const [loading, setLoading] = useState(false);

  const handleDelete = async () => {
    setLoading(true);
    try {
      await deleteUser(user);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()} placement="center">
      <Dialog.Backdrop />

      <Dialog.Positioner>
        <Dialog.Content>
          <Dialog.Header>{t("deleteUser")}</Dialog.Header>
          <Dialog.CloseTrigger />

          <Dialog.Body>
            <Trans
              i18nKey="deleteUserConfirm"
              values={{ account_number: user.account_number }}
            >
              Are you sure you want to delete user
              <b>{user.account_number}</b>?
            </Trans>
          </Dialog.Body>

          <Dialog.Footer gap={2}>
            <Button variant="outline" onClick={onClose}>
              {t("cancel")}
            </Button>
            <Button
              colorPalette="red"
              loading={loading}          // v3 prop
              onClick={handleDelete}
            >
              {t("delete")}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
};
