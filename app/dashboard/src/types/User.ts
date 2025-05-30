export type Status =
  | "active"
  | "disabled"
  | "limited"
  | "expired"
  | "on_hold"
  | "error"
  | "connecting"
  | "connected";

export type ProxyKeys = ("vmess" | "vless" | "trojan" | "shadowsocks")[];

export type ProxyType = {
  vmess?: {
    id?: string;
  };
  vless?: {
    id?: string;
    flow?: string;
  };
  trojan?: {
    password?: string;
  };
  shadowsocks?: {
    password?: string;
    method?: string;
  };
};

export type DataLimitResetStrategy =
  | "no_reset"
  | "day"
  | "week"
  | "month"
  | "year";

export type UserInbounds = {
  [key: string]: string[];
};

export type User = {
  proxies: ProxyType;
  expire: number | null;
  data_limit: number | null;
  data_limit_reset_strategy: DataLimitResetStrategy;
  on_hold_expire_duration: number | null;
  lifetime_used_traffic: number;
  account_number: string; // Primary identifier
  used_traffic: number;
  status: Status;
  links: string[];
  subscription_url: string;
  inbounds: UserInbounds;
  note: string;
  online_at: string | null; // Changed to string | null for more flexibility if API can return null
  // Consider adding other fields if they are consistently part of the User object from backend
  // email?: string; // if it's still used anywhere
  // created_at?: string;
  // admin_id?: number;
  // admin_username?: string;
  // sub_last_user_agent?: string;
  // sub_updated_at?: string;
  // id?: number;
};

export type UserCreate = Pick<
  User,
  | "inbounds"
  | "proxies"
  | "expire"
  | "data_limit"
  | "data_limit_reset_strategy"
  | "on_hold_expire_duration"
  | "account_number"
  | "status"
  | "note"
  // Add other fields necessary for user creation if `User` type has more non-optional fields
>;

// This type seems to be for the admin user's own details or system settings
export type UserApi = {
  discord_webhook: string; // Corrected typo from discord_webook
  is_sudo: boolean;
  telegram_id: number | string;
  account_number: string; // Admin's own account_number
};

export type UseGetUserReturn = {
  userData: UserApi | undefined; // Allow undefined for initial state or if fetch fails
  getUserIsPending: boolean;
  getUserIsSuccess: boolean;
  getUserIsError: boolean;
  getUserError: Error | null;
};