import { User as XrayUser } from "./User";
import { Node as XrayNode } from "./node";

// Client Portal User - represents a user who can log into the client portal
export interface ClientPortalUser {
    id: number;
    email: string;
    username: string;
    created_at: string;
    is_active: boolean;
    account_number: string;
    status: string;
    data_limit: number | null;
    expire: string;
    sub_link: string;
    qr_code_url_list: string[];
    xray_user?: XrayUser; // The associated xray/v2ray user if one exists
    plan?: {
        id: string;
        name: string;
        description: string;
        price: number;
        duration_days: number;
        data_limit: number | null;
        features: string[];
    } | null;
}

// Response from POST /api/client-portal/login
export interface ClientLoginApiResponse {
    access_token: string;
    token_type: string;
    user: ClientPortalUser;
}

// Structure for PlanResponse from GET /client-portal/account/plans
export interface ClientPlan {
    id: string;
    name: string;
    description: string;
    price: number;
    duration_days: number;
    data_limit: number | null; // Bytes, null for unlimited
    stripe_price_id?: string | null;
    features: string[];
}

// Structure for NodeResponse from GET /api/client-portal/servers
// This extends the base XrayNode with client-specific fields
export interface ClientNode extends XrayNode {
    is_available: boolean;
    current_load?: number; // Server load percentage
    location?: string;    // Server location
    ping?: number;        // Latency in ms
}

// Response from GET /api/client-portal/account
export interface ClientAccountDetailsResponse {
    user: ClientPortalUser;
    active_node?: ClientNode | null;
    available_nodes: ClientNode[];
    stripe_public_key?: string | null;
    mock_stripe_payment: boolean;
    frontend_url?: string | null;
    subscription_status?: 'active' | 'inactive' | 'expired' | 'pending';
    subscription_expires_at?: string | null;
}

// Response from POST /client-portal/create-checkout-session
export interface ClientStripeCheckoutSessionResponse {
    url: string;
    mock?: boolean;
    error?: string;
}

// Response from POST /client-portal/account/activate
export interface ClientActivateDirectPlanResponse {
    user: ClientPortalUser;
    xray_user: XrayUser;
    message: string;
}

// Error response type for client portal API calls
export interface ClientPortalErrorResponse {
    detail: string;
    code?: string;
    status_code: number;
}