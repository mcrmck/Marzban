import { FetchOptions, $fetch as ohMyFetch } from "ofetch";
import { getAuthToken } from "../utils/authStorage";

export const $fetch = ohMyFetch.create({
  baseURL: import.meta.env.VITE_BASE_API,
});

const createFetcher = () => {
  const getHeaders = (): Record<string, string> => {
    const token = getAuthToken();
    console.debug('HTTP: Raw token from storage:', token);
    
    if (token && token !== 'null' && token !== 'undefined') {
      console.debug('HTTP: Using auth token:', token.substring(0, 20) + '...');
      return { Authorization: `Bearer ${token}` };
    } else {
      console.debug('HTTP: No valid auth token found, token value:', token);
      return {};
    }
  };

  return {
    get: <T>(url: string, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { 
        ...options, 
        method: 'GET', 
        headers: { ...getHeaders(), ...options.headers } 
      });
    },
    post: <T>(url: string, data?: any, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { 
        ...options, 
        method: 'POST', 
        body: data, 
        headers: { ...getHeaders(), ...options.headers } 
      });
    },
    put: <T>(url: string, data?: any, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { 
        ...options, 
        method: 'PUT', 
        body: data, 
        headers: { ...getHeaders(), ...options.headers } 
      });
    },
    delete: <T>(url: string, options: FetchOptions<"json"> = {}) => {
      return $fetch<T>(url, { 
        ...options, 
        method: 'DELETE', 
        headers: { ...getHeaders(), ...options.headers } 
      });
    },
  };
};

export const fetcher = createFetcher();
export const fetch = fetcher;
