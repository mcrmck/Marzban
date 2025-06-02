import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import {
    saveClientAuthToken,
    getClientAuthToken,
    removeClientAuthToken,
} from "../utils/clientAuthStorage";
import {
    loginClientApi,
    getClientAccountDetailsApi,
    getPlansApi,
    getClientServersApi,
    createStripeCheckoutSessionApi,
    activateDirectPlanApi,
    logoutClientApi,
} from "../service/clientPortalApi";
import {
    ClientAccountDetailsResponse,
    ClientPlan,
    ClientNode,
    ClientStripeCheckoutSessionResponse,
    ClientPortalUser
} from "../types/clientPortal";

export interface ClientPortalState {
    clientToken: string | null;
    clientDetails: ClientAccountDetailsResponse | null;
    plans: ClientPlan[];
    servers: ClientNode[];
    isLoadingAuth: boolean;
    isLoadingDetails: boolean;
    isLoadingPlans: boolean;
    isLoadingServers: boolean;
    isLoadingPayment: boolean;
    error: string | null;

    // Selectors
    isAuthenticated: () => boolean;
    getActiveNode: () => ClientNode | null;
    getAvailableNodes: () => ClientNode[];
    getCurrentPlan: () => ClientPlan | null;

    // Actions
    initializeAuth: () => void;
    login: (accountNumber: string) => Promise<boolean>;
    logout: () => Promise<void>;
    fetchClientDetails: () => Promise<void>;
    fetchPlans: () => Promise<void>;
    fetchServers: () => Promise<void>;
    initiateStripeCheckout: (planId: string) => Promise<ClientStripeCheckoutSessionResponse | null>;
    activatePlanDirectly: (planId: string) => Promise<ClientPortalUser | null>;
    clearError: () => void;
}

export const useClientPortalStore = create(
    subscribeWithSelector<ClientPortalState>((set, get) => ({
        clientToken: null,
        clientDetails: null,
        plans: [],
        servers: [],
        isLoadingAuth: false,
        isLoadingDetails: false,
        isLoadingPlans: false,
        isLoadingServers: false,
        isLoadingPayment: false,
        error: null,

        // Selectors
        isAuthenticated: () => !!get().clientToken && !!get().clientDetails,
        getActiveNode: () => get().clientDetails?.active_node || null,
        getAvailableNodes: () => get().clientDetails?.available_nodes || [],
        getCurrentPlan: () => {
            const details = get().clientDetails;
            if (!details?.user.xray_user) return null;
            return get().plans.find(plan =>
                plan.id === details.user.xray_user?.account_number
            ) || null;
        },

        // Actions
        initializeAuth: () => {
            const token = getClientAuthToken();
            if (token) {
                set({ clientToken: token });
                // Optionally fetch details if token exists
                get().fetchClientDetails().catch(err => {
                    console.error("Failed to fetch client details on init:", err);
                    get().logout();
                });
            }
        },

        login: async (accountNumber: string) => {
            set({ isLoadingAuth: true, error: null });
            try {
                const response = await loginClientApi(accountNumber);
                saveClientAuthToken(response.access_token);
                set({ clientToken: response.access_token, isLoadingAuth: false });
                await get().fetchClientDetails();
                return true;
            } catch (error: any) {
                console.error("Client login failed:", error);
                removeClientAuthToken();
                set({
                    isLoadingAuth: false,
                    error: error.detail || "Login failed. Please check account number.",
                    clientToken: null,
                    clientDetails: null,
                });
                return false;
            }
        },

        logout: async () => {
            try {
                await logoutClientApi();
            } catch (error) {
                console.error("Logout API call failed:", error);
            } finally {
                removeClientAuthToken();
                set({
                    clientToken: null,
                    clientDetails: null,
                    plans: [],
                    servers: [],
                    error: null,
                });
            }
        },

        fetchClientDetails: async () => {
            if (!get().clientToken) return;

            set({ isLoadingDetails: true, error: null });
            try {
                const details = await getClientAccountDetailsApi();
                set({ clientDetails: details, isLoadingDetails: false });
            } catch (error: any) {
                console.error("Failed to fetch client details:", error);
                if (error.status === 401 || error.status === 403) {
                    get().logout();
                }
                set({
                    isLoadingDetails: false,
                    error: error.detail || "Failed to load account details.",
                });
            }
        },

        fetchPlans: async () => {
            set({ isLoadingPlans: true, error: null });
            try {
                const plansData = await getPlansApi();
                set({ plans: plansData, isLoadingPlans: false });
            } catch (error: any) {
                console.error("Failed to fetch plans:", error);
                set({
                    isLoadingPlans: false,
                    error: error.detail || "Failed to load plans."
                });
            }
        },

        fetchServers: async () => {
            if (!get().clientToken) return;

            set({ isLoadingServers: true, error: null });
            try {
                const serversData = await getClientServersApi();
                set({ servers: serversData, isLoadingServers: false });
            } catch (error: any) {
                console.error("Failed to fetch servers:", error);
                if (error.status === 401 || error.status === 403) {
                    get().logout();
                }
                set({
                    isLoadingServers: false,
                    error: error.detail || "Failed to load servers."
                });
            }
        },

        initiateStripeCheckout: async (planId: string) => {
            if (!get().isAuthenticated()) {
                set({ error: "Please login to proceed with payment." });
                return null;
            }

            set({ isLoadingPayment: true, error: null });
            try {
                const response = await createStripeCheckoutSessionApi(planId);
                set({ isLoadingPayment: false });

                if (response.url) {
                    return response;
                } else if (response.error) {
                    set({ error: response.error });
                    return null;
                }
                return response;
            } catch (error: any) {
                console.error("Stripe checkout initiation failed:", error);
                set({
                    isLoadingPayment: false,
                    error: error.detail || "Payment initiation failed."
                });
                return null;
            }
        },

        activatePlanDirectly: async (planId: string) => {
            if (!get().isAuthenticated()) {
                set({ error: "Please login to activate a plan." });
                return null;
            }

            set({ isLoadingPayment: true, error: null });
            try {
                const response = await activateDirectPlanApi(planId);
                await get().fetchClientDetails();
                set({ isLoadingPayment: false });
                return response.user;
            } catch (error: any) {
                console.error("Direct plan activation failed:", error);
                set({
                    isLoadingPayment: false,
                    error: error.detail || "Plan activation failed."
                });
                return null;
            }
        },

        clearError: () => set({ error: null }),
    }))
);