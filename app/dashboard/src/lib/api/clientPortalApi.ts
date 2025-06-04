import { FetchOptions, $fetch as ohMyFetch, FetchContext, FetchResponse } from "ofetch";
import { getClientAuthToken } from "../utils/clientAuthStorage";
import {
    ClientLoginApiResponse,
    ClientAccountDetailsResponse,
    ClientPlan,
    ClientNode,
    ClientStripeCheckoutSessionResponse,
    ClientActivateDirectPlanResponse
} from "../types/clientPortal";

// Base URL for client portal APIs
const CLIENT_PORTAL_API_BASE_URL = "/api/portal";


const clientPortalFetch = ohMyFetch.create({
    baseURL: CLIENT_PORTAL_API_BASE_URL,
    // Add default error handling
    async onResponseError(context: FetchContext<any, any> & { response: FetchResponse<any> }) {
        const error = context.response._data;
        console.error("[Client Portal API Error]", error);
        throw error;
    }
});

const createClientPortalFetcher = <T = any>(
    url: string,
    ops: FetchOptions<"json"> & { body?: any } = {}
) => {
    const token = getClientAuthToken();
    const headers: Record<string, string> = {};

    if (ops.headers) {
        Object.assign(headers, ops.headers);
    }

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    // Smart Content-Type handling
    if (ops.method && ['POST', 'PUT', 'PATCH'].includes(ops.method.toUpperCase()) && ops.body) {
        if (!headers["Content-Type"]) {
            if (ops.body instanceof URLSearchParams) {
                // For URLSearchParams, ofetch handles Content-Type automatically
            } else if (ops.body instanceof FormData) {
                // For FormData, browser handles Content-Type automatically
            } else {
                // Default to JSON for other object types
                headers["Content-Type"] = "application/json";
            }
        }
    }

    return clientPortalFetch<T>(url, { ...ops, headers });
};

// Authentication
export const registerClientApi = (): Promise<ClientLoginApiResponse> => {
    return createClientPortalFetcher<ClientLoginApiResponse>(
        "/register",
        {
            method: "POST"
        }
    );
};

export const loginClientApi = (accountNumber: string): Promise<ClientLoginApiResponse> => {
    return createClientPortalFetcher<ClientLoginApiResponse>(
        "/login",
        {
            method: "POST",
            body: { account_number: accountNumber }
        }
    );
};

// Account Details
export const getClientAccountDetailsApi = (): Promise<ClientAccountDetailsResponse> => {
    return createClientPortalFetcher<ClientAccountDetailsResponse>("/account");
};

// Plans
export const getPlansApi = (): Promise<ClientPlan[]> => {
    return createClientPortalFetcher<ClientPlan[]>("/account/plans");
};

// Servers
export const getClientServersApi = (): Promise<ClientNode[]> => {
    return createClientPortalFetcher<ClientNode[]>("/servers");
};

// Stripe Checkout
export const createStripeCheckoutSessionApi = (planId: string): Promise<ClientStripeCheckoutSessionResponse> => {
    return createClientPortalFetcher<ClientStripeCheckoutSessionResponse>("/create-checkout-session", {
        method: "POST",
        body: { plan_id: planId }
    });
};

// Direct Plan Activation
export const activateDirectPlanApi = (planId: string): Promise<ClientActivateDirectPlanResponse> => {
    return createClientPortalFetcher<ClientActivateDirectPlanResponse>("/account/activate", {
        method: "POST",
        body: { plan_id: planId }
    });
};

// Logout
export const logoutClientApi = (): Promise<void> => {
    return createClientPortalFetcher<void>("/logout", {
        method: "POST"
    });
};