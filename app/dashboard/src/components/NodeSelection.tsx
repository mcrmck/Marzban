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
} from '@chakra-ui/react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { fetch } from 'service/http';
import { useTranslation } from 'react-i18next';
import { Node } from 'types/node';

interface NodeSelectionProps {
  username: string;
}

export const NodeSelection: React.FC<NodeSelectionProps> = ({ username }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: nodes, isLoading } = useQuery<Node[]>(
    ['nodes'],
    () => fetch('/nodes').then((res) => res.json())
  );

  const { data: selectedNodes } = useQuery<Node[]>(
    ['user-nodes', username],
    () => fetch(`/user/${username}/nodes`).then((res) => res.json())
  );

  const addNodeMutation = useMutation(
    (nodeId: number) =>
      fetch(`/user/${username}/nodes/${nodeId}`, { method: 'POST' }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['user-nodes', username]);
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
      fetch(`/user/${username}/nodes/${nodeId}`, { method: 'DELETE' }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['user-nodes', username]);
        toast({
          title: t('nodeSelection.nodeRemoved'),
          status: 'success',
          duration: 3000,
        });
      },
    }
  );

  const handleNodeToggle = (node: Node) => {
    const isSelected = selectedNodes?.some((n) => n.id === node.id);
    if (isSelected) {
      removeNodeMutation.mutate(node.id);
    } else {
      addNodeMutation.mutate(node.id);
    }
  };

  if (isLoading) {
    return <Box>Loading...</Box>;
  }

  return (
    <Box>
      <Heading size="md" mb={4}>
        {t('nodeSelection.title')}
      </Heading>
      <Table variant="simple">
        <Thead>
          <Tr>
            <Th>{t('nodeSelection.name')}</Th>
            <Th>{t('nodeSelection.address')}</Th>
            <Th>{t('nodeSelection.status')}</Th>
            <Th>{t('nodeSelection.action')}</Th>
          </Tr>
        </Thead>
        <Tbody>
          {nodes?.map((node) => (
            <Tr key={node.id}>
              <Td>{node.name}</Td>
              <Td>{node.address}</Td>
              <Td>{node.status}</Td>
              <Td>
                <Checkbox
                  isChecked={selectedNodes?.some((n) => n.id === node.id)}
                  onChange={() => handleNodeToggle(node)}
                />
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
};