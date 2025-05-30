import { StatisticsQueryKey } from "components/Statistics";
import { fetch } from "service/http";
import { User, UserCreate } from "types/User";
import { queryClient } from "utils/react-query";
import { getUsersPerPageLimitSize } from "utils/userPreferenceStorage";
import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";

console.log("🚨 TEST CONSOLE LOG - DASHBOARD CONTEXT LOADED 🚨"); // Super obvious test log
console.warn("DashboardContext.tsx loaded"); // This should show up when the file loads

export type FilterType = {
  search?: string;
  limit?: number;
  offset?: number;
  sort: string;
  status?: "active" | "disabled" | "limited" | "expired" | "on_hold";
};
export type ProtocolType = "vmess" | "vless" | "trojan" | "shadowsocks";

export type FilterUsageType = {
  start?: string;
  end?: string;
};

export type InboundType = {
  tag: string;
  protocol: ProtocolType;
  network: string;
  tls: string;
  port?: number;
};
export type Inbounds = Map<ProtocolType, InboundType[]>;

type DashboardStateType = {
  isCreatingNewUser: boolean;
  editingUser: User | null | undefined;
  deletingUser: User | null;
  version: string | null;
  users: {
    users: User[];
    total: number;
  };
  inbounds: Inbounds;
  loading: boolean;
  filters: FilterType;
  subscribeUrl: string | null;
  QRcodeLinks: string[] | null;
  isEditingHosts: boolean;
  isEditingNodes: boolean;
  isShowingNodesUsage: boolean;
  isResetingAllUsage: boolean;
  resetUsageUser: User | null;
  revokeSubscriptionUser: User | null;
  isEditingCore: boolean;
  onCreateUser: (isOpen: boolean) => void;
  onEditingUser: (user: User | null) => void;
  onDeletingUser: (user: User | null) => void;
  onResetAllUsage: (isResetingAllUsage: boolean) => void;
  refetchUsers: () => void;
  resetAllUsage: () => Promise<void>;
  onFilterChange: (filters: Partial<FilterType>) => void;
  deleteUser: (user: User) => Promise<void>;
  createUser: (user: UserCreate) => Promise<void>;
  editUser: (user: UserCreate) => Promise<User | void>; // Adjusted return type
  fetchUserUsage: (user: User, query: FilterUsageType) => Promise<any>;
  setQRCode: (links: string[] | null) => void;
  setSubLink: (subscribeURL: string | null) => void;
  onEditingHosts: (isEditingHosts: boolean) => void;
  onEditingNodes: (isEditingNodes: boolean) => void;
  onShowingNodesUsage: (isShowingNodesUsage: boolean) => void;
  resetDataUsage: (user: User) => Promise<void>;
  revokeSubscription: (user: User) => Promise<User | void>; // Adjusted return type
  resetUserUsage: (account_number: string) => Promise<void>;
  onResetUsageUser: (user: User | null) => void;
  onRevokeSubscriptionUser: (user: User | null) => void;
};

const fetchUsers = (query: FilterType): Promise<{ users: User[]; total: number }> => {
  const activeQuery: Partial<FilterType> = {};
  // Type-safe iteration and building of activeQuery
  (Object.keys(query) as Array<keyof FilterType>).forEach(key => {
    const value = query[key];
    if (value !== undefined && value !== "") {
      // @ts-ignore because TS can't infer that key and value[key] match after the check
      activeQuery[key] = value;
    }
  });

  useDashboard.setState({ loading: true });
  return fetch("/users", { query: activeQuery })
    .then((response: { users: User[]; total: number }) => {
      useDashboard.setState({ users: response });
      return response;
    })
    .catch(error => {
      console.error("Failed to fetch users:", error);
      useDashboard.setState({ users: { users: [], total: 0 } }); // Reset on error
      return { users: [], total: 0 }; // Return a default structure on error
    })
    .finally(() => {
      useDashboard.setState({ loading: false });
    });
};

export const fetchInbounds = () => {
  useDashboard.setState({ loading: true });
  return fetch("/inbounds")
    .then((inboundsData: Record<ProtocolType, InboundType[]>) => {
      useDashboard.setState({
        inbounds: new Map(Object.entries(inboundsData)) as Inbounds,
      });
    })
    .catch(error => {
      console.error("Failed to fetch inbounds:", error);
      useDashboard.setState({ inbounds: new Map() }); // Reset on error
    })
    .finally(() => {
      useDashboard.setState({ loading: false });
    });
};

export const useDashboard = create(
  subscribeWithSelector<DashboardStateType>((set, get) => ({
    version: null,
    editingUser: null,
    deletingUser: null,
    isCreatingNewUser: false,
    QRcodeLinks: null,
    subscribeUrl: null,
    users: {
      users: [],
      total: 0,
    },
    loading: true,
    isResetingAllUsage: false,
    isEditingHosts: false,
    isEditingNodes: false,
    isShowingNodesUsage: false,
    resetUsageUser: null,
    revokeSubscriptionUser: null,
    filters: { // Corrected: using 'search' and ensuring all FilterType optional fields are potentially here
      search: "",
      limit: getUsersPerPageLimitSize(),
      offset: 0, // Explicitly initialize offset
      sort: "-created_at",
      status: undefined, // Explicitly initialize status
    },
    inbounds: new Map(),
    isEditingCore: false,
    refetchUsers: () => {
      fetchUsers(get().filters);
    },
    resetAllUsage: () => {
      return fetch(`/users/reset`, { method: "POST" }).then(() => {
        get().onResetAllUsage(false);
        get().refetchUsers();
      });
    },
    onResetAllUsage: (isResetingAllUsage) => set({ isResetingAllUsage }),
    onCreateUser: (isCreatingNewUser) => set({ isCreatingNewUser, editingUser: null }),
    onEditingUser: (editingUser) => {
      set({ editingUser, isCreatingNewUser: false });
    },
    onDeletingUser: (deletingUser) => {
      set({ deletingUser });
    },
    onFilterChange: (newFilters) => {
      const currentFilters = get().filters;
      const updatedFilters: FilterType = { // Ensure updatedFilters conforms to FilterType
        search: newFilters.search !== undefined ? newFilters.search : currentFilters.search,
        limit: newFilters.limit !== undefined ? newFilters.limit : currentFilters.limit,
        offset: currentFilters.offset, // Keep current offset by default
        sort: newFilters.sort !== undefined ? newFilters.sort : currentFilters.sort,
        status: newFilters.status !== undefined ? newFilters.status : currentFilters.status,
      };

      // Reset offset if filters that affect total items change
      if (
        (newFilters.search !== undefined && newFilters.search !== currentFilters.search) ||
        (newFilters.status !== undefined && newFilters.status !== currentFilters.status) ||
        (newFilters.limit !== undefined && newFilters.limit !== currentFilters.limit && currentFilters.offset !== 0) // Only reset if limit changes and offset was not already 0
      ) {
        updatedFilters.offset = 0;
      }

      // If only page (offset) changes, keep other filters
      if (newFilters.offset !== undefined && Object.keys(newFilters).length === 1) {
        updatedFilters.offset = newFilters.offset;
      }


      set({ filters: updatedFilters });
      get().refetchUsers();
    },
    setQRCode: (QRcodeLinks) => {
      set({ QRcodeLinks });
    },
    deleteUser: (user: User) => {
      const accountNumber = user?.account_number; // Use optional chaining
      console.log("deleteUser called with:", { user, accountNumber }); // Debug log
      if (!accountNumber || accountNumber === "undefined" || accountNumber.trim() === "") {
        console.error("DashboardContext: deleteUser - Invalid account_number:", accountNumber, "User:", user);
        return Promise.reject("Invalid account_number for deleteUser.");
      }
      return fetch(`/user/${accountNumber}`, { method: "DELETE" }).then(() => {
        set({ deletingUser: null });
        get().refetchUsers();
        queryClient.invalidateQueries(StatisticsQueryKey);
      });
    },

    createUser: (body: UserCreate) => {
      // This function doesn't use account_number in the path, so it's okay.
      return fetch(`/user`, { method: "POST", body }).then(() => {
        set({ isCreatingNewUser: false });
        get().refetchUsers();
        queryClient.invalidateQueries(StatisticsQueryKey);
      });
    },
    editUser: (body: UserCreate) => {
      const accountNumber = body?.account_number; // UserCreate might have optional account_number
      console.log("editUser called with:", { body, accountNumber }); // Debug log
      if (!accountNumber || accountNumber === "undefined" || accountNumber.trim() === "") {
        console.error("DashboardContext: editUser - Invalid account_number:", accountNumber, "Body:", body);
        return Promise.reject("Invalid account_number for editUser.");
      }
      return fetch(`/user/${accountNumber}`, { method: "PUT", body }).then(
        (updatedUser: User) => {
          get().onEditingUser(null);
          get().refetchUsers();
          return updatedUser;
        }
      );
    },
    fetchUserUsage: (user: User, query: FilterUsageType) => {
      debugger; // Debug point 1: Function entry
      console.log("fetchUserUsage STARTED"); // This should show up when the function is called
      const accountNumber = user?.account_number;
      console.log("fetchUserUsage called with:", { user, accountNumber, query }); // Debug log
      if (!accountNumber || accountNumber === "undefined" || accountNumber.trim() === "") {
        debugger; // Debug point 2: Invalid account number
        console.error("DashboardContext: fetchUserUsage - Invalid account_number:", accountNumber, "User:", user);
        return Promise.reject("Invalid account_number for fetchUserUsage.");
      }
      const activeQuery: Partial<FilterUsageType> = {};
      (Object.keys(query) as Array<keyof FilterUsageType>).forEach(key => {
        if (query[key]) activeQuery[key] = query[key];
      });
      debugger; // Debug point 3: Before fetch request
      return fetch(`/user/${accountNumber}/usage`, { method: "GET", query: activeQuery });
    },

    onEditingHosts: (isEditingHosts: boolean) => {
      set({ isEditingHosts });
    },
    onEditingNodes: (isEditingNodes: boolean) => {
      set({ isEditingNodes });
    },
    onShowingNodesUsage: (isShowingNodesUsage: boolean) => {
      set({ isShowingNodesUsage });
    },
    setSubLink: (subscribeUrl) => {
      set({ subscribeUrl });
    },
    resetDataUsage: (user: User) => {
      const accountNumber = user?.account_number;
      console.log("resetDataUsage called with:", { user, accountNumber }); // Debug log
      if (!accountNumber || accountNumber === "undefined" || accountNumber.trim() === "") {
        console.error("DashboardContext: resetDataUsage - Invalid account_number:", accountNumber, "User:", user);
        return Promise.reject("Invalid account_number for resetDataUsage.");
      }
      return fetch(`/user/${accountNumber}/reset`, { method: "POST" }).then(() => {
        get().refetchUsers();
      });
    },
    revokeSubscription: (user: User) => {
      const accountNumber = user?.account_number;
      console.log("revokeSubscription called with:", { user, accountNumber }); // Debug log
      if (!accountNumber || accountNumber === "undefined" || accountNumber.trim() === "") {
        console.error("DashboardContext: revokeSubscription - Invalid account_number:", accountNumber, "User:", user);
        return Promise.reject("Invalid account_number for revokeSubscription.");
      }
      return fetch(`/user/${accountNumber}/revoke_sub`, {
        method: "POST",
      }).then((updatedUserResponse: any) => {
        set({ revokeSubscriptionUser: null });
        if (updatedUserResponse && typeof updatedUserResponse === 'object' && 'account_number' in updatedUserResponse) {
            const updatedUser = updatedUserResponse as User;
            set(state => ({
                users: {
                    ...state.users,
                    users: state.users.users.map(u => u.account_number === updatedUser.account_number ? updatedUser : u),
                },
                editingUser: state.editingUser?.account_number === updatedUser.account_number ? updatedUser : state.editingUser
            }));
        } else {
            get().refetchUsers();
        }
        return updatedUserResponse;
      });
    },
    resetUserUsage: (account_number_param: string) => { // Renamed param to avoid confusion
      console.log("resetUserUsage called with:", { account_number_param }); // Debug log
      if (!account_number_param || account_number_param === "undefined" || account_number_param.trim() === "") {
        console.error("DashboardContext: resetUserUsage - Invalid account_number string provided:", account_number_param);
        return Promise.reject("Invalid account_number string for resetUserUsage.");
      }
      return fetch(`/user/${account_number_param}/reset`, { method: "POST" }).then(() => {
        get().refetchUsers();
      });
    },

    onResetUsageUser: (user: User | null) => {
      set({ resetUsageUser: user });
    },
    onRevokeSubscriptionUser: (user: User | null) => {
      set({ revokeSubscriptionUser: user });
    },
  }))
);