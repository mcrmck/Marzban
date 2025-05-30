import React from 'react';
import {
  Box,
  Button,
  Checkbox,
  Flex,
  Heading,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  useToast,
  Spinner, // Added for loading state
} from '@chakra-ui/react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { fetch } from 'service/http'; // Assuming this is your configured fetch
import { useTranslation } from 'react-i18next';
import { Node } from 'types/node'; // Ensure this Node type is correct

// Updated props to use accountNumber
interface NodeSelectionProps {
  accountNumber: string;
}

export const NodeSelection: React.FC<NodeSelectionProps> = ({ accountNumber }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: allNodes, isLoading: isLoadingNodes } = useQuery<Node[]>(
    ['nodes'], // Query key for all available nodes
    () => fetch('/nodes').then((res) => res.json()) // API endpoint to get all nodes
  );

  // Query key for nodes associated with the specific user (using accountNumber)
  const userNodesQueryKey = ['user-nodes', accountNumber];
  const { data: selectedNodes, isLoading: isLoadingSelectedNodes } = useQuery<Node[]>(
    userNodesQueryKey,
    () => fetch(`/user/${accountNumber}/nodes`).then((res) => res.json()), // API endpoint using accountNumber
    { enabled: !!accountNumber } // Only run if accountNumber is available
  );

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries(userNodesQueryKey); // Invalidate user's specific nodes list
      // Optionally, invalidate all nodes list if selection affects some global state of nodes, though unlikely
      // queryClient.invalidateQueries(['nodes']);
    },
    onError: (error: any) => {
      toast({
        title: t('nodeSelection.error'),
        description: error?.message || t('nodeSelection.genericError'),
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const addNodeMutation = useMutation(
    (nodeId: number) =>
      fetch(`/user/${accountNumber}/nodes/${nodeId}`, { method: 'POST' }), // API endpoint using accountNumber
    {
      ...mutationOptions,
      onSuccess: (...args) => {
        mutationOptions.onSuccess();
        toast({
          title: t('nodeSelection.nodeAdded'),
          status: 'success',
          duration: 3000,
        });
      },
    }
  );

  const removeNodeMutation = useMutation(
    (nodeId: number) =>
      fetch(`/user/${accountNumber}/nodes/${nodeId}`, { method: 'DELETE' }), // API endpoint using accountNumber
    {
      ...mutationOptions,
      onSuccess: (...args) => {
        mutationOptions.onSuccess();
        toast({
          title: t('nodeSelection.nodeRemoved'),
          status: 'success',
          duration: 3000,
        });
      },
    }
  );

  const handleNodeToggle = (node: Node) => {
    if (!accountNumber) return; // Guard against missing accountNumber

    const isSelected = selectedNodes?.some((n) => n.id === node.id);
    if (isSelected) {
      removeNodeMutation.mutate(node.id);
    } else {
      addNodeMutation.mutate(node.id);
    }
  };

  if (isLoadingNodes || isLoadingSelectedNodes) {
    return <Box display="flex" justifyContent="center" alignItems="center" p={5}><Spinner /> Loading nodes...</Box>;
  }

  return (
    <Box>
      <Heading size="md" mb={4}>
        {t('nodeSelection.title')}
      </Heading>
      <Table variant="simple" size="sm">
        <Thead>
          <Tr>
            <Th>{t('nodeSelection.name')}</Th>
            <Th>{t('nodeSelection.address')}</Th>
            <Th>{t('nodeSelection.status')}</Th>
            <Th textAlign="center">{t('nodeSelection.select')}</Th>
          </Tr>
        </Thead>
        <Tbody>
          {allNodes?.map((node) => (
            <Tr key={node.id}>
              <Td>{node.name}</Td>
              <Td>{node.address}</Td>
              <Td>{node.status || 'N/A'}</Td>
              <Td textAlign="center">
                <Checkbox
                  isChecked={selectedNodes?.some((n) => n.id === node.id)}
                  onChange={() => handleNodeToggle(node)}
                  isDisabled={addNodeMutation.isLoading || removeNodeMutation.isLoading}
                />
              </Td>
            </Tr>
          ))}
          {(!allNodes || allNodes.length === 0) && (
            <Tr><Td colSpan={4}>{t('nodeSelection.noNodesAvailable')}</Td></Tr>
          )}
        </Tbody>
      </Table>
    </Box>
  );
};