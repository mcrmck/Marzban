import {
  Button,
  chakra,
  Dialog,
  Text,
} from "@chakra-ui/react";
import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { useDashboard } from "../../lib/stores/DashboardContext";
import { FC, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { User } from "../../lib/types/User";

const ResetIcon = chakra(ArrowPathIcon);   // v3: no `baseStyle` option

type Props = {
  open: boolean;           // v3 prop names
  onClose: () => void;
  user: User;
};

export const RevokeSubscriptionDialog: FC<Props> = ({
  open,
  onClose,
  user,
}) => {
  const { t } = useTranslation();
  const { revokeSubscription } = useDashboard();
  const [loading, setLoading] = useState(false);

  const handleRevoke = async () => {
    setLoading(true);
    try {
      await revokeSubscription(user);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => !v && onClose()}
      placement="center"
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          <Dialog.Header>
            <ResetIcon w={5} h={5} me={2} />
            {t("revokeSubscription")}
          </Dialog.Header>

          <Dialog.CloseTrigger />

          <Dialog.Body>
            <Text>
              <Trans
                i18nKey="revokeSubscriptionConfirm"
                values={{ account_number: user.account_number }}
              >
                Are you sure you want to revoke the subscription for user
                <b>{user.account_number}</b>?
              </Trans>
            </Text>
          </Dialog.Body>

          <Dialog.Footer gap={2}>
            <Button variant="ghost" onClick={onClose}>
              {t("cancel")}
            </Button>
            <Button
              colorPalette="primary"
              onClick={handleRevoke}
              loading={loading}   // v3 prop
            >
              {t("revoke")}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
};
