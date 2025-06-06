import { useQuery } from "@tanstack/react-query";
import { fetch } from "../api/http";
import { z } from "zod";
import { create } from "zustand";
import { FilterUsageType, useDashboard } from "./DashboardContext";

export const NodeSchema = z.object({
  name: z.string().min(1),
  address: z.string().min(1),
  port: z
    .number()
    .min(1)
    .or(z.string().transform((v) => parseFloat(v))),
  api_port: z
    .number()
    .min(1)
    .or(z.string().transform((v) => parseFloat(v))),
  xray_version: z.string().nullable().optional(),
  id: z.number().nullable().optional(),
  status: z
    .enum(["connected", "connecting", "error", "disabled"])
    .nullable()
    .optional(),
  message: z.string().nullable().optional(),
  usage_coefficient: z.number().or(z.string().transform((v) => parseFloat(v))),
  panel_client_cert: z.string().optional(),
  panel_client_key: z.string().optional(),
});

export type NodeType = z.infer<typeof NodeSchema>;

export const getNodeDefaultValues = (): NodeType => ({
  name: "",
  address: "",
  port: 62050,
  api_port: 62051,
  xray_version: "",
  usage_coefficient: 1,
  panel_client_cert: "",
  panel_client_key: "",
});

export const FetchNodesQueryKey = ["fetch-nodes-query-key"] as const;

export type NodeStore = {
  nodes: NodeType[];
  addNode: (node: NodeType) => Promise<unknown>;
  fetchNodes: () => Promise<NodeType[]>;
  fetchNodesUsage: (query: FilterUsageType) => Promise<{ usages: any[] }>;
  updateNode: (node: NodeType) => Promise<unknown>;
  reconnectNode: (node: NodeType) => Promise<unknown>;
  deletingNode?: NodeType | null;
  deleteNode: () => Promise<unknown>;
  setDeletingNode: (node: NodeType | null) => void;
};

export const useNodesQuery = () => {
  const { isEditingNodes } = useDashboard();
  return useQuery({
    queryKey: FetchNodesQueryKey,
    queryFn: useNodes.getState().fetchNodes,
    refetchInterval: isEditingNodes ? 3000 : undefined,
    refetchOnWindowFocus: false,
  });
};

export const useNodes = create<NodeStore>((set, get) => ({
  nodes: [],
  addNode(body) {
    return fetch.post("/node", body);
  },
  fetchNodes() {
    return fetch.get<NodeType[]>("/nodes");
  },
  fetchNodesUsage(query: FilterUsageType) {
    return fetch.get("/nodes/usage", { query });
  },
  updateNode(body) {
    return fetch.put(`/node/${body.id}`, body);
  },
  setDeletingNode(node) {
    set({ deletingNode: node });
  },
  reconnectNode(body) {
    return fetch.post(`/node/${body.id}/reconnect`);
  },
  deleteNode: () => {
    return fetch.delete(`/node/${get().deletingNode?.id}`);
  },
}));
