import { Button, Dialog, Text } from "@chakra-ui/react";
import { ArrowPathIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { FC, useState } from "react";
import { useDashboard } from "../../lib/stores/DashboardContext";
import { useTranslation } from "react-i18next";

/* -------------------------------------------------------------------------- */
/* Icon                                                                       */
/* -------------------------------------------------------------------------- */

const ResetIcon = () => <ArrowPathIcon className="w-5 h-5" />;

/* -------------------------------------------------------------------------- */
/* Props                                                                      */
/* -------------------------------------------------------------------------- */

export interface ResetUserUsageModalProps {
  open: boolean;
  onClose: () => void;
  user: { account_number: string };
}

/* -------------------------------------------------------------------------- */
/* Component                                                                  */
/* -------------------------------------------------------------------------- */

export const ResetUserUsageModal: FC<ResetUserUsageModalProps> = ({ open, onClose, user }) => {
  const { t } = useTranslation();
  const { resetUserUsage } = useDashboard();
  const [loading, setLoading] = useState(false);

  const handleReset = async () => {
    setLoading(true);
    try {
      await resetUserUsage(user.account_number);
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(d) => !d.open && onClose()} role="alertdialog">
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          {/* Header */}
          <Dialog.Header p={6} borderBottomWidth="1px">
            <Text fontWeight="semibold" fontSize="lg">
              {t("resetUserUsage")}
            </Text>
            <Dialog.CloseTrigger asChild>
              <button aria-label={t("close")} className="absolute top-4 end-4">
                <XMarkIcon className="w-4 h-4" />
              </button>
            </Dialog.CloseTrigger>
          </Dialog.Header>

          {/* Body */}
          <Dialog.Body p={6}>
            <Text>
              {t("resetUserUsageConfirm", { account_number: user.account_number })}
            </Text>
          </Dialog.Body>

          {/* Footer */}
          <Dialog.Footer p={4} gap={3} display="flex" justifyContent="flex-end" borderTopWidth="1px">
            <Button variant="ghost" onClick={onClose} size="sm">
              {t("cancel")}
            </Button>
            <Button
              colorPalette="primary"
              size="sm"
              onClick={handleReset}
              loading={loading}
            >
              <ResetIcon />
              {t("reset")}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
};
