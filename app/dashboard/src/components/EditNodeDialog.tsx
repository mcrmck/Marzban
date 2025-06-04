import {
  Dialog,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Text,
} from "@chakra-ui/react";
import { FC } from "react";
import { useTranslation } from "react-i18next";
import { NodeForm } from "./NodeForm";
import { NodeServicesConfigurator } from "./NodeServicesConfigurator";
import { useNodes, NodeType } from "../lib/stores/NodesContext";

type Props = {
  open: boolean;          // v3 prop name
  onClose: () => void;
  node?: NodeType | null;
};

export const EditNodeDialog: FC<Props> = ({ open, onClose, node }) => {
  const { t } = useTranslation();
  const { addNode, updateNode } = useNodes();

  const handleSubmit = async (values: NodeType) => {
    if (node) await updateNode(values);
    else await addNode(values);
    onClose();
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => !v && onClose()}
      placement="center"
    >
      <Dialog.Backdrop bg="blackAlpha.300" backdropFilter="blur(10px)" />

      <Dialog.Positioner>
        <Dialog.Content w="full" maxW="xl" mx={3}>
          <Dialog.Header pt={6}>
            <Text fontWeight="semibold" fontSize="lg">
              {node ? t("nodes.editNode") : t("nodes.addNewNode")}
            </Text>
          </Dialog.Header>

          <Dialog.CloseTrigger mt={3} />

          <Dialog.Body pb={6}>
            <Tabs.Root defaultValue="basic">
              <TabsList>
                <TabsTrigger value="basic">
                  {t("nodes.basicSettings")}
                </TabsTrigger>
                {node && (
                  <TabsTrigger value="services">
                    {t("nodes.services")}
                  </TabsTrigger>
                )}
              </TabsList>

              <TabsContent value="basic">
                <NodeForm
                  initialValues={node}
                  onSubmit={handleSubmit}
                  submitText={node ? t("update") : t("add")}
                />
              </TabsContent>

              {node && node.id && (
                <TabsContent value="services">
                  <NodeServicesConfigurator nodeId={node.id} />
                </TabsContent>
              )}
            </Tabs.Root>
          </Dialog.Body>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
};
