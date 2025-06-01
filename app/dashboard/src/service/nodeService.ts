import { fetcher } from './http';
import {
    NodeServiceConfigurationResponse,
    NodeServiceConfigurationCreate,
    NodeServiceConfigurationUpdate,
} from '../types/NodeService';

export const getServicesForNode = (nodeId: number): Promise<NodeServiceConfigurationResponse[]> => {
    return fetcher(`/api/nodes/${nodeId}/services/`);
};

export const addServiceToNode = (
    nodeId: number,
    serviceData: NodeServiceConfigurationCreate
): Promise<NodeServiceConfigurationResponse> => {
    return fetcher(`/api/nodes/${nodeId}/services/`, {
        method: 'POST',
        body: serviceData,
    });
};

export const updateServiceOnNode = (
    nodeId: number,
    serviceId: number,
    serviceData: NodeServiceConfigurationUpdate
): Promise<NodeServiceConfigurationResponse> => {
    return fetcher(`/api/nodes/${nodeId}/services/${serviceId}`, {
        method: 'PUT',
        body: serviceData,
    });
};

export const deleteServiceOnNode = (
    nodeId: number,
    serviceId: number
): Promise<void> => {
    return fetcher(`/api/nodes/${nodeId}/services/${serviceId}`, {
        method: 'DELETE',
    });
};