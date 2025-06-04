import React from 'react';
import {
  Box,
  Heading,
  Spinner,
} from '@chakra-ui/react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetch } from '../lib/api/http';
import { useTranslation } from 'react-i18next';
import { Node } from '../lib/types/node';
import { toaster } from "@/components/ui/toaster";
import { Table } from '@chakra-ui/react';
import { Checkbox } from '@chakra-ui/react';

interface NodeSelectionProps {
  accountNumber: string;
}

export const NodeSelection: React.FC<NodeSelectionProps> = ({ accountNumber }) => {
  const { t } = useTranslation();
  // createToast is now imported directly
  const queryClient = useQueryClient();

  const { data: nodes, isLoading } = useQuery({
    queryKey: ['nodes'],
    queryFn: () => fetch.get<Node[]>('/api/core/api/nodes'),
  });

  const userNodesQueryKey = ['user-nodes', accountNumber];
  const { data: selectedNodes, isLoading: isLoadingSelectedNodes } = useQuery<Node[]>({
    queryKey: userNodesQueryKey,
    queryFn: () => fetch.get<Node[]>(`/user/${accountNumber}/nodes`),
    enabled: !!accountNumber
  });

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userNodesQueryKey });
    },
    onError: (error: any) => {
      toaster.create({
        title: t('nodeSelection.error'),
        description: error?.message || t('nodeSelection.genericError'),
        type: 'error',
        duration: 5000,
        closable: true,
      });
    }
  };

  const addNodeMutation = useMutation({
    mutationFn: (nodeId: number) => fetch.post(`/user/${accountNumber}/nodes/${nodeId}`),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess();
      toaster.create({
        title: t('nodeSelection.nodeAdded'),
        type: 'success',
        duration: 3000,
        closable: true,
      });
    },
  });

  const removeNodeMutation = useMutation({
    mutationFn: (nodeId: number) => fetch.delete(`/user/${accountNumber}/nodes/${nodeId}`),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess();
      toaster.create({
        title: t('nodeSelection.nodeRemoved'),
        type: 'success',
        duration: 3000,
        closable: true,
      });
    },
  });

  const handleNodeToggle = (node: Node) => {
    if (!accountNumber) return;

    const isSelected = selectedNodes?.some((n: Node) => n.id === node.id);
    if (isSelected) {
      removeNodeMutation.mutate(node.id);
    } else {
      addNodeMutation.mutate(node.id);
    }
  };

  if (isLoading || isLoadingSelectedNodes) {
    return <Box display="flex" justifyContent="center" alignItems="center" p={5}><Spinner /> Loading nodes...</Box>;
  }

  return (
    <Box>
      <Heading size="md" mb={4}>
        {t('nodeSelection.title')}
      </Heading>
      <Table.Root>
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader>{t('nodeSelection.name')}</Table.ColumnHeader>
            <Table.ColumnHeader>{t('nodeSelection.address')}</Table.ColumnHeader>
            <Table.ColumnHeader>{t('nodeSelection.status')}</Table.ColumnHeader>
            <Table.ColumnHeader textAlign="center">{t('nodeSelection.select')}</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {nodes?.map((node: Node) => (
            <Table.Row key={node.id}>
              <Table.Cell>{node.name}</Table.Cell>
              <Table.Cell>{node.address}</Table.Cell>
              <Table.Cell>{node.status || 'N/A'}</Table.Cell>
              <Table.Cell textAlign="center">
                <Checkbox.Root
                  checked={selectedNodes?.some((n: Node) => n.id === node.id)}
                  onChange={() => handleNodeToggle(node)}
                  disabled={addNodeMutation.isPending || removeNodeMutation.isPending}
                />
              </Table.Cell>
            </Table.Row>
          ))}
          {(!nodes || nodes.length === 0) && (
            <Table.Row>
              <Table.Cell colSpan={4}>{t('nodeSelection.noNodesAvailable')}</Table.Cell>
            </Table.Row>
          )}
        </Table.Body>
      </Table.Root>
    </Box>
  );
};