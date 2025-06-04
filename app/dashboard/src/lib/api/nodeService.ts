import { fetcher } from './http';
import {
    NodeServiceConfigurationResponse,
    NodeServiceConfigurationCreate,
    NodeServiceConfigurationUpdate,
} from '../types/NodeService';

export const getServicesForNode = (nodeId: number): Promise<NodeServiceConfigurationResponse[]> => {
    return fetcher.get(`/nodes/${nodeId}/services/`);
};

export const addServiceToNode = (
    nodeId: number,
    serviceData: NodeServiceConfigurationCreate
): Promise<NodeServiceConfigurationResponse> => {
    return fetcher.post(`/nodes/${nodeId}/services/`, serviceData);
};

export const updateServiceOnNode = (
    nodeId: number,
    serviceId: number,
    serviceData: NodeServiceConfigurationUpdate
): Promise<NodeServiceConfigurationResponse> => {
    return fetcher.put(`/nodes/${nodeId}/services/${serviceId}`, serviceData);
};

export const deleteServiceOnNode = (
    nodeId: number,
    serviceId: number
): Promise<void> => {
    return fetcher.delete(`/nodes/${nodeId}/services/${serviceId}`);
};