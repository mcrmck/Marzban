import { FetchOptions, $fetch as ohMyFetch } from "ofetch";
import { getAuthToken } from "../utils/authStorage";

export const $fetch = ohMyFetch.create({
  baseURL: import.meta.env.VITE_BASE_API,
});

const createFetcher = () => {
  const getHeaders = () => {
    const token = getAuthToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  return {
    get: <T>(url: string, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { ...options, method: 'GET', headers: getHeaders() });
    },
    post: <T>(url: string, data?: any, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { ...options, method: 'POST', body: data, headers: getHeaders() });
    },
    put: <T>(url: string, data?: any, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { ...options, method: 'PUT', body: data, headers: getHeaders() });
    },
    delete: <T>(url: string, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { ...options, method: 'DELETE', headers: getHeaders() });
    },
  };
};

export const fetcher = createFetcher();
export const fetch = fetcher;
