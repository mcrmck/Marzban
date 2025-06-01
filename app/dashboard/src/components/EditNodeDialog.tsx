import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  VStack,
  Text,
} from "@chakra-ui/react";
import { FC } from "react";
import { useTranslation } from "react-i18next";
import { NodeForm } from "./NodeForm";
import { NodeServicesConfigurator } from "./NodeServicesConfigurator";
import { useNodes } from "contexts/NodesContext";
import { NodeType } from "contexts/NodesContext";

interface EditNodeDialogProps {
  isOpen: boolean;
  onClose: () => void;
  node?: NodeType | null;
}

export const EditNodeDialog: FC<EditNodeDialogProps> = ({
  isOpen,
  onClose,
  node,
}) => {
  const { t } = useTranslation();
  const { addNode, updateNode } = useNodes();

  const handleSubmit = async (values: NodeType) => {
    if (node) {
      await updateNode(values);
    } else {
      await addNode(values);
    }
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay bg="blackAlpha.300" backdropFilter="blur(10px)" />
      <ModalContent mx="3" w="full">
        <ModalHeader pt={6}>
          <Text fontWeight="semibold" fontSize="lg">
            {node ? t("nodes.editNode") : t("nodes.addNewNode")}
          </Text>
        </ModalHeader>
        <ModalCloseButton mt={3} />
        <ModalBody pb={6}>
          <Tabs>
            <TabList>
              <Tab>{t("nodes.basicSettings")}</Tab>
              {node && <Tab>{t("nodes.services")}</Tab>}
            </TabList>

            <TabPanels>
              <TabPanel>
                <NodeForm
                  initialValues={node}
                  onSubmit={handleSubmit}
                  submitText={node ? t("update") : t("add")}
                />
              </TabPanel>
              {node && node.id && (
                <TabPanel>
                  <NodeServicesConfigurator nodeId={node.id} />
                </TabPanel>
              )}
            </TabPanels>
          </Tabs>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};