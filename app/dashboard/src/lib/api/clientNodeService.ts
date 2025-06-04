import { fetcher } from './http';
import { NodeServiceConfigurationResponse } from '../types/NodeService';

export interface ClientNodeActivationResponse {
  connection_string: string;
  qr_code?: string;
  config_file?: string;
}

export const activateNodeForClient = (
  accountNumber: string,
  nodeId: number,
  serviceId: number
): Promise<ClientNodeActivationResponse> => {
  return fetcher.post(`/api/core/api/user/${accountNumber}/node/activate`);
};

export const getClientActiveNode = (
  accountNumber: string
): Promise<{
  node_id: number;
  service_id: number;
  service: NodeServiceConfigurationResponse;
}> => {
  return fetcher.get(`/api/core/api/user/${accountNumber}`);
};