import React, { useState, useEffect, ChangeEvent, FormEvent } from 'react';
import {
    Box,
    Button,
    IconButton,
    Input,
    VStack,
    HStack,
    useDisclosure,
} from '@chakra-ui/react';
import { Plus, Edit, Trash } from 'lucide-react';
import {
    NodeServiceConfigurationResponse,
    NodeServiceConfigurationCreate,
    NodeServiceConfigurationUpdate,
    ProtocolType,
    NetworkType,
    SecurityType,
} from '../lib/types/NodeService';
import {
    getServicesForNode,
    addServiceToNode,
    updateServiceOnNode,
    deleteServiceOnNode,
} from '../lib/api/nodeService';
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

    const handleSubmit = async (e: FormEvent) => {
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

            <Box as="table" width="100%">
                <Box as="thead">
                    <Box as="tr">
                        <Box as="th">Service Name</Box>
                        <Box as="th">Protocol</Box>
                        <Box as="th">Port</Box>
                        <Box as="th">Network</Box>
                        <Box as="th">Security</Box>
                        <Box as="th">Enabled</Box>
                        <Box as="th">Actions</Box>
                    </Box>
                </Box>
                <Box as="tbody">
                    {services.map((service) => (
                        <Box as="tr" key={service.id}>
                            <Box as="td">{service.service_name}</Box>
                            <Box as="td">{service.protocol_type}</Box>
                            <Box as="td">{service.listen_port}</Box>
                            <Box as="td">{service.network_type || 'TCP'}</Box>
                            <Box as="td">{service.security_type}</Box>
                            <Box as="td">
                                <input
                                    type="checkbox"
                                    checked={service.enabled}
                                    onChange={(e: ChangeEvent<HTMLInputElement>) => handleToggleEnabled(service, e.target.checked)}
                                />
                            </Box>
                            <Box as="td">
                                <IconButton
                                    aria-label="Edit service"
                                    size="sm"
                                    mr={2}
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
                            </Box>
                        </Box>
                    ))}
                </Box>
            </Box>

            {open && (
                <Box
                    position="fixed"
                    top="0"
                    left="0"
                    right="0"
                    bottom="0"
                    bg="blackAlpha.600"
                    zIndex="modal"
                    onClick={onClose}
                >
                    <Box
                        position="absolute"
                        top="50%"
                        left="50%"
                        transform="translate(-50%, -50%)"
                        bg="white"
                        p={6}
                        borderRadius="md"
                        width="xl"
                        maxW="90vw"
                        maxH="90vh"
                        overflowY="auto"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
                            <Box fontSize="xl" fontWeight="bold">
                                {selectedService ? 'Edit Service' : 'Add Service'}
                            </Box>
                            <Button variant="ghost" onClick={onClose}>×</Button>
                        </Box>
                        <form onSubmit={handleSubmit}>
                            <VStack gap={4}>
                                <Box>
                                    <Box as="label">Service Name</Box>
                                    <Input
                                        value={formData.service_name}
                                        onChange={(e) => handleChange('service_name', e.target.value)}
                                    />
                                </Box>

                                <Box>
                                    <Box as="label">Protocol Type</Box>
                                    <select
                                        value={formData.protocol_type}
                                        onChange={(e: ChangeEvent<HTMLSelectElement>) => handleChange('protocol_type', e.target.value)}
                                    >
                                        {Object.values(ProtocolType).map((type) => (
                                            <option key={type} value={type}>
                                                {type}
                                            </option>
                                        ))}
                                    </select>
                                </Box>

                                <Box>
                                    <Box as="label">Listen Port</Box>
                                    <Input
                                        type="number"
                                        value={formData.listen_port}
                                        onChange={(e) => handleChange('listen_port', parseInt(e.target.value))}
                                    />
                                </Box>

                                <Box>
                                    <Box as="label">Network Type</Box>
                                    <select
                                        value={formData.network_type || NetworkType.TCP}
                                        onChange={(e: ChangeEvent<HTMLSelectElement>) => handleChange('network_type', e.target.value)}
                                    >
                                        {Object.values(NetworkType).map((type) => (
                                            <option key={type} value={type}>
                                                {type}
                                            </option>
                                        ))}
                                    </select>
                                </Box>

                                <Box>
                                    <Box as="label">Security Type</Box>
                                    <select
                                        value={formData.security_type}
                                        onChange={(e: ChangeEvent<HTMLSelectElement>) => handleChange('security_type', e.target.value)}
                                    >
                                        {Object.values(SecurityType).map((type) => (
                                            <option key={type} value={type}>
                                                {type}
                                            </option>
                                        ))}
                                    </select>
                                </Box>

                                <Box>
                                    <Box as="label">Advanced Protocol Settings</Box>
                                    <JsonEditor
                                        json={formData.advanced_protocol_settings || {}}
                                        onChange={handleJsonChange('advanced_protocol_settings')}
                                    />
                                </Box>

                                <Box>
                                    <Box as="label">Advanced Stream Settings</Box>
                                    <JsonEditor
                                        json={formData.advanced_stream_settings || {}}
                                        onChange={handleJsonChange('advanced_stream_settings')}
                                    />
                                </Box>

                                <Box>
                                    <Box as="label">Advanced TLS Settings</Box>
                                    <JsonEditor
                                        json={formData.advanced_tls_settings || {}}
                                        onChange={handleJsonChange('advanced_tls_settings')}
                                    />
                                </Box>

                                <Box>
                                    <Box as="label">Advanced REALITY Settings</Box>
                                    <JsonEditor
                                        json={formData.advanced_reality_settings || {}}
                                        onChange={handleJsonChange('advanced_reality_settings')}
                                    />
                                </Box>

                                <Box>
                                    <Box as="label">Sniffing Settings</Box>
                                    <JsonEditor
                                        json={formData.sniffing_settings || {}}
                                        onChange={handleJsonChange('sniffing_settings')}
                                    />
                                </Box>

                                <HStack gap={4} width="100%" justify="flex-end">
                                    <Button onClick={onClose}>Cancel</Button>
                                    <Button type="submit" colorScheme="blue">
                                        {selectedService ? 'Update' : 'Add'}
                                    </Button>
                                </HStack>
                            </VStack>
                        </form>
                    </Box>
                </Box>
            )}
        </Box>
    );
};