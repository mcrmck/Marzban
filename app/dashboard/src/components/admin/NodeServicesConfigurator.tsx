import React, { useState, useEffect } from 'react';
import {
    Box,
    Button,
    IconButton,
    Input,
    VStack,
    HStack,
    useDisclosure,
    Table,
    Dialog,
    Field,
    Select,
    Switch,
    Text,
    createListCollection,
} from '@chakra-ui/react';
import { Plus, Edit, Trash } from 'lucide-react';
import {
    NodeServiceConfigurationResponse,
    NodeServiceConfigurationCreate,
    NodeServiceConfigurationUpdate,
    ProtocolType,
    NetworkType,
    SecurityType,
} from '../../lib/types/NodeService';
import {
    getServicesForNode,
    addServiceToNode,
    updateServiceOnNode,
    deleteServiceOnNode,
} from '../../lib/api/nodeService';
import { JsonEditor } from './JsonEditor';

interface NodeServicesConfiguratorProps {
    nodeId: number;
}

export const NodeServicesConfigurator: React.FC<NodeServicesConfiguratorProps> = ({ nodeId }) => {
    const [services, setServices] = useState<NodeServiceConfigurationResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedService, setSelectedService] = useState<NodeServiceConfigurationResponse | null>(null);
    const [formData, setFormData] = useState<NodeServiceConfigurationCreate>({
        service_name: '',
        enabled: true,
        protocol_type: ProtocolType.VLESS,
        listen_port: 443,
        security_type: SecurityType.TLS,
    });
    const { open, onOpen, onClose } = useDisclosure();

    const protocolCollection = createListCollection({
        items: Object.values(ProtocolType).map(type => ({
            label: type,
            value: type,
        })),
    });

    const networkCollection = createListCollection({
        items: Object.values(NetworkType).map(type => ({
            label: type,
            value: type,
        })),
    });

    const securityCollection = createListCollection({
        items: Object.values(SecurityType).map(type => ({
            label: type,
            value: type,
        })),
    });

    const fetchServices = async () => {
        try {
            setLoading(true);
            const data = await getServicesForNode(nodeId);
            setServices(data);
        } catch (error) {
            console.error('Error fetching services:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchServices();
    }, [nodeId]);

    const handleAddService = () => {
        setSelectedService(null);
        onOpen();
    };

    const handleEditService = (service: NodeServiceConfigurationResponse) => {
        setSelectedService(service);
        onOpen();
    };

    const handleDeleteService = async (serviceId: number) => {
        if (window.confirm('Are you sure you want to delete this service?')) {
            try {
                await deleteServiceOnNode(nodeId, serviceId);
                fetchServices();
            } catch (error) {
                console.error('Error deleting service:', error);
            }
        }
    };

    const handleChange = (field: keyof NodeServiceConfigurationCreate, value: any) => {
        setFormData(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleJsonChange = (field: keyof NodeServiceConfigurationCreate) => (value: string) => {
        try {
            const parsedValue = JSON.parse(value);
            handleChange(field, parsedValue);
        } catch (error) {
            // Invalid JSON, ignore
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (selectedService) {
                await updateServiceOnNode(nodeId, selectedService.id, formData as NodeServiceConfigurationUpdate);
            } else {
                await addServiceToNode(nodeId, formData as NodeServiceConfigurationCreate);
            }
            onClose();
            fetchServices();
        } catch (error) {
            console.error('Error saving service:', error);
        }
    };

    const handleToggleEnabled = async (service: NodeServiceConfigurationResponse, enabled: boolean) => {
        try {
            await updateServiceOnNode(nodeId, service.id, { ...service, enabled });
            fetchServices();
        } catch (error) {
            console.error('Error updating service:', error);
        }
    };

    return (
        <Box>
            <Button colorScheme="blue" mb={4} onClick={handleAddService}>
                <Plus />
                Add Service
            </Button>

            <Table.Root variant="outline">
                <Table.Header>
                    <Table.Row>
                        <Table.ColumnHeader>Service Name</Table.ColumnHeader>
                        <Table.ColumnHeader>Protocol</Table.ColumnHeader>
                        <Table.ColumnHeader>Port</Table.ColumnHeader>
                        <Table.ColumnHeader>Network</Table.ColumnHeader>
                        <Table.ColumnHeader>Security</Table.ColumnHeader>
                        <Table.ColumnHeader>Enabled</Table.ColumnHeader>
                        <Table.ColumnHeader>Actions</Table.ColumnHeader>
                    </Table.Row>
                </Table.Header>
                <Table.Body>
                    {services.map((service) => (
                        <Table.Row key={service.id}>
                            <Table.Cell>{service.service_name}</Table.Cell>
                            <Table.Cell>{service.protocol_type}</Table.Cell>
                            <Table.Cell>{service.listen_port}</Table.Cell>
                            <Table.Cell>{service.network_type || 'TCP'}</Table.Cell>
                            <Table.Cell>{service.security_type}</Table.Cell>
                            <Table.Cell>
                                <Switch.Root
                                    checked={service.enabled}
                                    onCheckedChange={(details) => handleToggleEnabled(service, details.checked)}
                                >
                                    <Switch.Control />
                                </Switch.Root>
                            </Table.Cell>
                            <Table.Cell>
                                <HStack gap={2}>
                                    <IconButton
                                        aria-label="Edit service"
                                        size="sm"
                                        onClick={() => handleEditService(service)}
                                    >
                                        <Edit />
                                    </IconButton>
                                    <IconButton
                                        aria-label="Delete service"
                                        size="sm"
                                        colorScheme="red"
                                        onClick={() => handleDeleteService(service.id)}
                                    >
                                        <Trash />
                                    </IconButton>
                                </HStack>
                            </Table.Cell>
                        </Table.Row>
                    ))}
                </Table.Body>
            </Table.Root>

            <Dialog.Root open={open} onOpenChange={(details) => !details.open && onClose()}>
                <Dialog.Backdrop bg="blackAlpha.300" backdropFilter="blur(10px)" />
                <Dialog.Positioner>
                    <Dialog.Content mx="3" w="full" maxW="2xl">
                        <Dialog.Header pt={6}>
                            <Text fontWeight="semibold" fontSize="lg">
                                {selectedService ? 'Edit Service' : 'Add Service'}
                            </Text>
                        </Dialog.Header>
                        <Dialog.CloseTrigger asChild>
                            <IconButton
                                aria-label="close"
                                size="sm"
                                variant="ghost"
                                pos="absolute"
                                top="3"
                                right="3"
                            >
                                <span>&times;</span>
                            </IconButton>
                        </Dialog.CloseTrigger>
                        <Dialog.Body pb={6}>
                            <form onSubmit={handleSubmit}>
                                <VStack gap={4}>
                                    <Field.Root>
                                        <Field.Label>Service Name</Field.Label>
                                        <Input
                                            value={formData.service_name}
                                            onChange={(e) => handleChange('service_name', e.target.value)}
                                        />
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Protocol Type</Field.Label>
                                        <Select.Root
                                            collection={protocolCollection}
                                            value={[formData.protocol_type]}
                                            onValueChange={(details) => handleChange('protocol_type', details.value[0])}
                                        >
                                            <Select.Trigger>
                                                <Select.ValueText />
                                            </Select.Trigger>
                                            <Select.Positioner>
                                                <Select.Content>
                                                    {protocolCollection.items.map((item) => (
                                                        <Select.Item key={item.value} item={item}>
                                                            {item.label}
                                                        </Select.Item>
                                                    ))}
                                                </Select.Content>
                                            </Select.Positioner>
                                        </Select.Root>
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Listen Port</Field.Label>
                                        <Input
                                            type="number"
                                            value={formData.listen_port}
                                            onChange={(e) => handleChange('listen_port', parseInt(e.target.value))}
                                        />
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Network Type</Field.Label>
                                        <Select.Root
                                            collection={networkCollection}
                                            value={[formData.network_type || NetworkType.TCP]}
                                            onValueChange={(details) => handleChange('network_type', details.value[0])}
                                        >
                                            <Select.Trigger>
                                                <Select.ValueText />
                                            </Select.Trigger>
                                            <Select.Positioner>
                                                <Select.Content>
                                                    {networkCollection.items.map((item) => (
                                                        <Select.Item key={item.value} item={item}>
                                                            {item.label}
                                                        </Select.Item>
                                                    ))}
                                                </Select.Content>
                                            </Select.Positioner>
                                        </Select.Root>
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Security Type</Field.Label>
                                        <Select.Root
                                            collection={securityCollection}
                                            value={[formData.security_type]}
                                            onValueChange={(details) => handleChange('security_type', details.value[0])}
                                        >
                                            <Select.Trigger>
                                                <Select.ValueText />
                                            </Select.Trigger>
                                            <Select.Positioner>
                                                <Select.Content>
                                                    {securityCollection.items.map((item) => (
                                                        <Select.Item key={item.value} item={item}>
                                                            {item.label}
                                                        </Select.Item>
                                                    ))}
                                                </Select.Content>
                                            </Select.Positioner>
                                        </Select.Root>
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Advanced Protocol Settings</Field.Label>
                                        <JsonEditor
                                            json={formData.advanced_protocol_settings || {}}
                                            onChange={handleJsonChange('advanced_protocol_settings')}
                                        />
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Advanced Stream Settings</Field.Label>
                                        <JsonEditor
                                            json={formData.advanced_stream_settings || {}}
                                            onChange={handleJsonChange('advanced_stream_settings')}
                                        />
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Advanced TLS Settings</Field.Label>
                                        <JsonEditor
                                            json={formData.advanced_tls_settings || {}}
                                            onChange={handleJsonChange('advanced_tls_settings')}
                                        />
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Advanced REALITY Settings</Field.Label>
                                        <JsonEditor
                                            json={formData.advanced_reality_settings || {}}
                                            onChange={handleJsonChange('advanced_reality_settings')}
                                        />
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Sniffing Settings</Field.Label>
                                        <JsonEditor
                                            json={formData.sniffing_settings || {}}
                                            onChange={handleJsonChange('sniffing_settings')}
                                        />
                                    </Field.Root>

                                    <HStack gap={4} width="100%" justify="flex-end">
                                        <Button onClick={onClose}>Cancel</Button>
                                        <Button type="submit" colorScheme="blue">
                                            {selectedService ? 'Update' : 'Add'}
                                        </Button>
                                    </HStack>
                                </VStack>
                            </form>
                        </Dialog.Body>
                    </Dialog.Content>
                </Dialog.Positioner>
            </Dialog.Root>
        </Box>
    );
};