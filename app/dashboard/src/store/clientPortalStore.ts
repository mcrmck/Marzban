import { create } from "zustand";
import { saveClientAuthToken, getClientAuthToken, removeClientAuthToken } from "../utils/clientAuthStorage";
import {
    loginClientApi,
    registerClientApi,
    getClientAccountDetailsApi,
    getPlansApi,
    getClientServersApi,
    createStripeCheckoutSessionApi,
    activateDirectPlanApi,
    logoutClientApi
} from "../service/clientPortalApi";
import {
    ClientPortalUser,
    ClientPlan,
    ClientNode,
    ClientAccountDetailsResponse
} from "../types/clientPortal";

interface ClientPortalState {
    // Auth state
    isAuthenticated: boolean;
    isLoadingAuth: boolean;
    error: string | null;
    initializeAuth: () => Promise<void>;
    register: () => Promise<boolean>;
    login: (accountNumber: string) => Promise<void>;
    logout: () => Promise<void>;

    // Client details
    clientDetails: ClientAccountDetailsResponse | null;
    isLoadingDetails: boolean;
    fetchClientDetails: () => Promise<void>;

    // Plans
    plans: ClientPlan[];
    isLoadingPlans: boolean;
    fetchPlans: () => Promise<void>;
    initiateStripeCheckout: (planId: string) => Promise<{ url: string } | null>;
    activatePlanDirectly: (planId: string) => Promise<void>;

    // Servers
    servers: ClientNode[];
    isLoadingServers: boolean;
    fetchServers: () => Promise<void>;
}

export const useClientPortalStore = create<ClientPortalState>((set, get) => ({
    // Auth state
    isAuthenticated: false,
    isLoadingAuth: false,
    error: null,

    initializeAuth: async () => {
        const token = getClientAuthToken();
        if (!token) {
            set({ isAuthenticated: false });
            return;
        }

        set({ isLoadingAuth: true });
        try {
            // Verify token by making a request to get client details
            await getClientAccountDetailsApi();
            set({ isAuthenticated: true });
        } catch (error) {
            removeClientAuthToken();
            set({ isAuthenticated: false });
        } finally {
            set({ isLoadingAuth: false });
        }
    },

    register: async () => {
        set({ isLoadingAuth: true, error: null });
        try {
            const response = await registerClientApi();
            saveClientAuthToken(response.access_token);
            set({ isAuthenticated: true });
            await get().fetchClientDetails();
            return true;
        } catch (error) {
            set({ error: "Failed to register account" });
            throw error;
        } finally {
            set({ isLoadingAuth: false });
        }
    },

    login: async (accountNumber: string) => {
        set({ isLoadingAuth: true, error: null });
        try {
            const response = await loginClientApi(accountNumber);
            saveClientAuthToken(response.access_token);
            set({ isAuthenticated: true });
            await get().fetchClientDetails();
        } catch (error) {
            set({ error: "Invalid account number" });
            throw error;
        } finally {
            set({ isLoadingAuth: false });
        }
    },

    logout: async () => {
        try {
            await logoutClientApi();
        } catch (error) {
            console.error("Logout failed:", error);
        } finally {
            removeClientAuthToken();
            set({ isAuthenticated: false, clientDetails: null });
        }
    },

    // Client details
    clientDetails: null,
    isLoadingDetails: false,

    fetchClientDetails: async () => {
        set({ isLoadingDetails: true });
        try {
            const data = await getClientAccountDetailsApi();
            set({ clientDetails: data });
        } catch (error) {
            set({ error: "Failed to fetch client details" });
            throw error;
        } finally {
            set({ isLoadingDetails: false });
        }
    },

    // Plans
    plans: [],
    isLoadingPlans: false,

    fetchPlans: async () => {
        set({ isLoadingPlans: true });
        try {
            const data = await getPlansApi();
            set({ plans: data });
        } catch (error) {
            set({ error: "Failed to fetch plans" });
            throw error;
        } finally {
            set({ isLoadingPlans: false });
        }
    },

    initiateStripeCheckout: async (planId: string) => {
        try {
            const data = await createStripeCheckoutSessionApi(planId);
            return data;
        } catch (error) {
            set({ error: "Failed to initiate checkout" });
            throw error;
        }
    },

    activatePlanDirectly: async (planId: string) => {
        try {
            await activateDirectPlanApi(planId);
            // Refresh client details after plan activation
            await get().fetchClientDetails();
        } catch (error) {
            set({ error: "Failed to activate plan" });
            throw error;
        }
    },

    // Servers
    servers: [],
    isLoadingServers: false,

    fetchServers: async () => {
        set({ isLoadingServers: true });
        try {
            const data = await getClientServersApi();
            set({ servers: data });
        } catch (error) {
            set({ error: "Failed to fetch servers" });
            throw error;
        } finally {
            set({ isLoadingServers: false });
        }
    },
}));