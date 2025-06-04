/**
 * Unified API client for both admin and client portals
 * Provides consistent HTTP interface with proper error handling
 */

import { ofetch } from "ofetch";
import { getAdminToken, getClientToken } from '../../lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export interface ApiConfig {
  baseURL: string;
  getToken: () => string | null;
  onError?: (error: any) => void;
}

export class ApiClient {
  private client;

  constructor(private config: ApiConfig) {
    this.client = ofetch.create({
      baseURL: config.baseURL,
      headers: {
        "Content-Type": "application/json",
      },
      onRequest: ({ options }) => {
        const token = this.config.getToken();
        if (token) {
          if (!options.headers) options.headers = new Headers();
          options.headers.append('Authorization',
            token.startsWith("Bearer ") ? token : `Bearer ${token}`);
        }
      },
      onResponseError: ({ error }) => {
        this.config.onError?.(error);
      },
    });
  }

  async get<T = any>(url: string, params?: Record<string, any>): Promise<T> {
    return this.client(url, { method: "GET", params });
  }

  async post<T = any>(url: string, data?: any): Promise<T> {
    return this.client(url, { method: "POST", body: data });
  }

  async put<T = any>(url: string, data?: any): Promise<T> {
    return this.client(url, { method: "PUT", body: data });
  }

  async patch<T = any>(url: string, data?: any): Promise<T> {
    return this.client(url, { method: "PATCH", body: data });
  }

  async delete<T = any>(url: string): Promise<T> {
    return this.client(url, { method: "DELETE" });
  }

  // File upload helper
  async upload<T = any>(url: string, formData: FormData): Promise<T> {
    return this.client(url, {
      method: "POST",
      body: formData,
      headers: {
        // Remove Content-Type to let browser set it with boundary
      },
    });
  }
}

const getHeaders = (token?: string | null): Headers => {
  const headers = new Headers();
  if (token) {
    headers.append('Authorization', `Bearer ${token}`);
  }
  return headers;
};

export const fetch = {
  get: async <T>(url: string, options: RequestInit = {}): Promise<T> => {
    const token = getClientToken();
    const headers = getHeaders(token);

    // Merge any additional headers from options
    if (options.headers) {
      Object.entries(options.headers).forEach(([key, value]) => {
        headers.append(key, value);
      });
    }

    const response = await window.fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers,
      method: 'GET',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  },
  // ... rest of the fetch methods ...
};