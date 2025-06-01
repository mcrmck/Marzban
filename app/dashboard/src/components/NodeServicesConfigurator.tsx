import React, { useState, useEffect, ChangeEvent, FormEvent } from 'react';
import {
    Box,
    Button,
    Table,
    Thead,
    Tbody,
    Tr,
    Th,
    Td,
    Switch,
    IconButton,
    useToast,
    Modal,
    ModalOverlay,
    ModalContent,
    ModalHeader,
    ModalBody,
    ModalCloseButton,
    FormControl,
    FormLabel,
    Input,
    Select,
    Textarea,
    VStack,
    HStack,
    useDisclosure,
} from '@chakra-ui/react';
import { EditIcon, DeleteIcon, AddIcon } from '@chakra-ui/icons';
import {
    NodeServiceConfigurationResponse,
    NodeServiceConfigurationCreate,
    NodeServiceConfigurationUpdate,
    ProtocolType,
    NetworkType,
    SecurityType,
} from '../types/NodeService';
import {
    getServicesForNode,
    addServiceToNode,
    updateServiceOnNode,
    deleteServiceOnNode,
} from '../service/nodeService';
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
    const { isOpen, onOpen, onClose } = useDisclosure();
    const toast = useToast();

    const fetchServices = async () => {
        try {
            setLoading(true);
            const data = await getServicesForNode(nodeId);
            setServices(data);
        } catch (error) {
            toast({
                title: 'Error fetching services',
                description: error instanceof Error ? error.message : 'Unknown error',
                status: 'error',
                duration: 5000,
                isClosable: true,
            });
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
                toast({
                    title: 'Service deleted',
                    status: 'success',
                    duration: 3000,
                });
                fetchServices();
            } catch (error) {
                toast({
                    title: 'Error deleting service',
                    description: error instanceof Error ? error.message : 'Unknown error',
                    status: 'error',
                    duration: 5000,
                });
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
                toast({
                    title: 'Service updated',
                    status: 'success',
                    duration: 3000,
                });
            } else {
                await addServiceToNode(nodeId, formData as NodeServiceConfigurationCreate);
                toast({
                    title: 'Service added',
                    status: 'success',
                    duration: 3000,
                });
            }
            onClose();
            fetchServices();
        } catch (error) {
            toast({
                title: 'Error saving service',
                description: error instanceof Error ? error.message : 'Unknown error',
                status: 'error',
                duration: 5000,
            });
        }
    };

    const handleToggleEnabled = async (service: NodeServiceConfigurationResponse, enabled: boolean) => {
        try {
            await updateServiceOnNode(nodeId, service.id, { ...service, enabled });
            toast({
                title: 'Service updated',
                status: 'success',
                duration: 3000,
            });
            fetchServices();
        } catch (error) {
            toast({
                title: 'Error updating service',
                description: error instanceof Error ? error.message : 'Unknown error',
                status: 'error',
                duration: 5000,
            });
        }
    };

    return (
        <Box>
            <Button leftIcon={<AddIcon />} colorScheme="blue" mb={4} onClick={handleAddService}>
                Add Service
            </Button>

            <Table variant="simple">
                <Thead>
                    <Tr>
                        <Th>Service Name</Th>
                        <Th>Protocol</Th>
                        <Th>Port</Th>
                        <Th>Network</Th>
                        <Th>Security</Th>
                        <Th>Enabled</Th>
                        <Th>Actions</Th>
                    </Tr>
                </Thead>
                <Tbody>
                    {services.map((service) => (
                        <Tr key={service.id}>
                            <Td>{service.service_name}</Td>
                            <Td>{service.protocol_type}</Td>
                            <Td>{service.listen_port}</Td>
                            <Td>{service.network_type || 'TCP'}</Td>
                            <Td>{service.security_type}</Td>
                            <Td>
                                <Switch
                                    isChecked={service.enabled}
                                    onChange={(e) => handleToggleEnabled(service, e.target.checked)}
                                />
                            </Td>
                            <Td>
                                <IconButton
                                    aria-label="Edit service"
                                    icon={<EditIcon />}
                                    size="sm"
                                    mr={2}
                                    onClick={() => handleEditService(service)}
                                />
                                <IconButton
                                    aria-label="Delete service"
                                    icon={<DeleteIcon />}
                                    size="sm"
                                    colorScheme="red"
                                    onClick={() => handleDeleteService(service.id)}
                                />
                            </Td>
                        </Tr>
                    ))}
                </Tbody>
            </Table>

            <Modal isOpen={isOpen} onClose={onClose} size="xl">
                <ModalOverlay />
                <ModalContent>
                    <ModalHeader>
                        {selectedService ? 'Edit Service' : 'Add Service'}
                    </ModalHeader>
                    <ModalCloseButton />
                    <ModalBody>
                        <form onSubmit={handleSubmit}>
                            <VStack spacing={4}>
                                <FormControl isRequired>
                                    <FormLabel>Service Name</FormLabel>
                                    <Input
                                        value={formData.service_name}
                                        onChange={(e) => handleChange('service_name', e.target.value)}
                                    />
                                </FormControl>

                                <FormControl isRequired>
                                    <FormLabel>Protocol Type</FormLabel>
                                    <Select
                                        value={formData.protocol_type}
                                        onChange={(e) => handleChange('protocol_type', e.target.value)}
                                    >
                                        {Object.values(ProtocolType).map((type) => (
                                            <option key={type} value={type}>
                                                {type}
                                            </option>
                                        ))}
                                    </Select>
                                </FormControl>

                                <FormControl isRequired>
                                    <FormLabel>Listen Port</FormLabel>
                                    <Input
                                        type="number"
                                        value={formData.listen_port}
                                        onChange={(e) => handleChange('listen_port', parseInt(e.target.value))}
                                    />
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Network Type</FormLabel>
                                    <Select
                                        value={formData.network_type || NetworkType.TCP}
                                        onChange={(e) => handleChange('network_type', e.target.value)}
                                    >
                                        {Object.values(NetworkType).map((type) => (
                                            <option key={type} value={type}>
                                                {type}
                                            </option>
                                        ))}
                                    </Select>
                                </FormControl>

                                <FormControl isRequired>
                                    <FormLabel>Security Type</FormLabel>
                                    <Select
                                        value={formData.security_type}
                                        onChange={(e) => handleChange('security_type', e.target.value)}
                                    >
                                        {Object.values(SecurityType).map((type) => (
                                            <option key={type} value={type}>
                                                {type}
                                            </option>
                                        ))}
                                    </Select>
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Advanced Protocol Settings</FormLabel>
                                    <JsonEditor
                                        json={formData.advanced_protocol_settings || {}}
                                        onChange={handleJsonChange('advanced_protocol_settings')}
                                    />
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Advanced Stream Settings</FormLabel>
                                    <JsonEditor
                                        json={formData.advanced_stream_settings || {}}
                                        onChange={handleJsonChange('advanced_stream_settings')}
                                    />
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Advanced TLS Settings</FormLabel>
                                    <JsonEditor
                                        json={formData.advanced_tls_settings || {}}
                                        onChange={handleJsonChange('advanced_tls_settings')}
                                    />
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Advanced REALITY Settings</FormLabel>
                                    <JsonEditor
                                        json={formData.advanced_reality_settings || {}}
                                        onChange={handleJsonChange('advanced_reality_settings')}
                                    />
                                </FormControl>

                                <FormControl>
                                    <FormLabel>Sniffing Settings</FormLabel>
                                    <JsonEditor
                                        json={formData.sniffing_settings || {}}
                                        onChange={handleJsonChange('sniffing_settings')}
                                    />
                                </FormControl>

                                <HStack spacing={4} width="100%" justify="flex-end">
                                    <Button onClick={onClose}>Cancel</Button>
                                    <Button type="submit" colorScheme="blue">
                                        {selectedService ? 'Update' : 'Add'}
                                    </Button>
                                </HStack>
                            </VStack>
                        </form>
                    </ModalBody>
                </ModalContent>
            </Modal>
        </Box>
    );
};