import {
  Button,
  Dialog,
  IconButton,
  Icon,
  Text,
} from "@chakra-ui/react";
import { toaster } from "@/components/ui/toaster";
import { FC, useState } from "react";
import { DocumentMinusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useDashboard } from "../lib/stores/DashboardContext";
import { useTranslation } from "react-i18next";

export type DeleteUserModalProps = {};

export const ResetAllUsageModal: FC<DeleteUserModalProps> = () => {
  const [loading, setLoading] = useState(false);
  const { isResetingAllUsage, onResetAllUsage, resetAllUsage } = useDashboard();
  const { t } = useTranslation();
  // toast function is replaced with createToast
  const onClose = () => {
    onResetAllUsage(false);
  };
  const onReset = () => {
    setLoading(true);
    resetAllUsage()
      .then(() => {
        toaster.create({
          title: t("resetAllUsage.success"),
          type: "success",
          closable: true,
          duration: 3000,
        });
      })
      .catch(() => {
        toaster.create({
          title: t("resetAllUsage.error"),
          type: "error",
          closable: true,
          duration: 3000,
        });
      })
      .finally(() => {
        setLoading(false);
      });
  };
  return (
    <Dialog.Root open={isResetingAllUsage} onOpenChange={(d) => !d.open && onClose()}>
      <Dialog.Backdrop bg="blackAlpha.300" backdropFilter="blur(10px)" />
      <Dialog.Positioner>
        <Dialog.Content mx="3">
          <Dialog.Header pt={6}>
            <Icon color="red">
              <DocumentMinusIcon className="w-5 h-5" />
            </Icon>
          </Dialog.Header>
          <Dialog.CloseTrigger asChild>
            <IconButton aria-label="close" size="sm" variant="ghost" mt={3}>
              <XMarkIcon className="w-4 h-4" />
            </IconButton>
          </Dialog.CloseTrigger>
          <Dialog.Body>
            <Text fontWeight="semibold" fontSize="lg">
              {t("resetAllUsage.title")}
            </Text>
            {isResetingAllUsage && (
              <Text
                mt={1}
                fontSize="sm"
                _dark={{ color: "gray.400" }}
                color="gray.600"
              >
                {t("resetAllUsage.prompt")}
              </Text>
            )}
          </Dialog.Body>
          <Dialog.Footer display="flex">
            <Button size="sm" onClick={onClose} mr={3} w="full" variant="outline">
              {t("cancel")}
            </Button>
            <Button
              size="sm"
              w="full"
              colorPalette="red"
              onClick={onReset}
              loading={loading}
            >
              {t("reset")}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
};
