import { NodeServiceConfigurationResponse } from './NodeService';

export interface Node {
  id: number;
  name: string;
  address: string;
  status: string;
  api_port: number;
  xray_version?: string;
  service_configurations: NodeServiceConfigurationResponse[];
}