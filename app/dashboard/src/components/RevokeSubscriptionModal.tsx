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
import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { useDashboard } from "contexts/DashboardContext";
import { FC, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import { User } from "types/User"; // Added import

export const ResetIcon = chakra(ArrowPathIcon, {
  baseStyle: {
    w: 5,
    h: 5,
  },
});

export type RevokeSubscriptionModalProps = {
  isOpen: boolean;
  onClose: () => void;
  user: User; // Changed from { account_number: string } to User
};

export const RevokeSubscriptionModal: FC<RevokeSubscriptionModalProps> = ({ isOpen, onClose, user }) => {
  const { t } = useTranslation();
  const { revokeSubscription } = useDashboard();
  const [isRevoking, setIsRevoking] = useState(false);

  const handleRevoke = async () => {
    setIsRevoking(true);
    try {
      await revokeSubscription(user); // Changed from user.account_number to user
      onClose();
    } catch (error) {
      console.error(error);
    } finally {
      setIsRevoking(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>{t("revokeSubscription")}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Text>
            <Trans i18nKey="revokeSubscriptionConfirm" values={{ account_number: user.account_number }}>
              Are you sure you want to revoke the subscription for user {{ account_number: user.account_number }}?
            </Trans>
          </Text>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button
            colorScheme="primary"
            onClick={handleRevoke}
            isLoading={isRevoking}
          >
            {t("revoke")}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};