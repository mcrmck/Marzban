import {
  Box,
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
  Toast,
  useToast,
} from "@chakra-ui/react";
import { FC, useEffect, useRef, useState } from "react";
import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { Icon } from "./Icon";
import { useDashboard } from "contexts/DashboardContext";
import { useTranslation, Trans } from "react-i18next";

export const ResetIcon = chakra(ArrowPathIcon, {
  baseStyle: {
    w: 5,
    h: 5,
  },
});

export type ResetUserUsageModalProps = {
  isOpen: boolean;
  onClose: () => void;
  user: any;
};

export const ResetUserUsageModal: FC<ResetUserUsageModalProps> = ({ isOpen, onClose, user }) => {
  const { t } = useTranslation();
  const { resetUserUsage } = useDashboard();
  const [isResetting, setIsResetting] = useState(false);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      await resetUserUsage(user.account_number);
      onClose();
    } catch (error) {
      console.error(error);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{t("resetUserUsage")}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Text>
            {t("resetUserUsageConfirm", { account_number: user.account_number })}
          </Text>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button
            colorScheme="primary"
            onClick={handleReset}
            isLoading={isResetting}
          >
            {t("reset")}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};
