/**
 * Custom hook for API calls with React Query integration
 * Provides standardized data fetching patterns
 */

import { useQuery, useMutation, useQueryClient, type UseQueryOptions, type UseMutationOptions } from "@tanstack/react-query";
import { ApiClient } from "../services/api";

export interface UseApiOptions<T> extends Omit<UseQueryOptions<T>, "queryKey" | "queryFn"> {
  queryKey: (string | number | boolean)[];
}

export const useApi = <T = any>(
  apiClient: ApiClient,
  endpoint: string,
  options?: UseApiOptions<T>
) => {
  return useQuery({
    queryKey: options?.queryKey || [endpoint],
    queryFn: () => apiClient.get<T>(endpoint),
    ...options,
  });
};

interface MutationVariables {
  endpoint: string;
  data?: any;
}

export const useApiMutation = <TData = any, TVariables = MutationVariables>(
  apiClient: ApiClient,
  method: "post" | "put" | "patch" | "delete" = "post",
  options?: UseMutationOptions<TData, Error, TVariables>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (variables: TVariables) => {
      const { endpoint, data } = variables as MutationVariables;
      switch (method) {
        case "post":
          return apiClient.post<TData>(endpoint, data);
        case "put":
          return apiClient.put<TData>(endpoint, data);
        case "patch":
          return apiClient.patch<TData>(endpoint, data);
        case "delete":
          return apiClient.delete<TData>(endpoint);
        default:
          throw new Error(`Unsupported method: ${method}`);
      }
    },
    onSuccess: (data, variables, context) => {
      // Invalidate related queries on successful mutation
      queryClient.invalidateQueries();
      options?.onSuccess?.(data, variables, context);
    },
    ...options,
  });
};

// Specialized hooks for common patterns
export const useApiPost = <TData = any, TVariables = any>(
  apiClient: ApiClient,
  options?: UseMutationOptions<TData, Error, TVariables>
) => useApiMutation(apiClient, "post", options);

export const useApiPut = <TData = any, TVariables = any>(
  apiClient: ApiClient,
  options?: UseMutationOptions<TData, Error, TVariables>
) => useApiMutation(apiClient, "put", options);

export const useApiDelete = <TData = any, TVariables = any>(
  apiClient: ApiClient,
  options?: UseMutationOptions<TData, Error, TVariables>
) => useApiMutation(apiClient, "delete", options);