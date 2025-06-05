/* DashboardContext.tsx
   -------------------- */

   import { StatisticsQueryKey } from "../../components/admin/Statistics";
   import { fetch as http } from "../api/http";                    // ⬅️ use named import
   import { User, UserCreate } from "../types/User";
   import { queryClient } from "../utils/react-query";
   import { getUsersPerPageLimitSize } from "../utils/userPreferenceStorage";

   import { create } from "zustand";
   import { subscribeWithSelector } from "zustand/middleware";

   /* ------------------------------------------------------------------ */
   /* ----------------------------- types ------------------------------ */
   /* ------------------------------------------------------------------ */

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
     /* ui-state ------------------------------------------------------- */
     isCreatingNewUser: boolean;
     editingUser: User | null;
     deletingUser: User | null;
     isEditingNodes: boolean;
     isShowingNodesUsage: boolean;
     isEditingCore: boolean;
     isResetingAllUsage: boolean;
     resetUsageUser: User | null;
     revokeSubscriptionUser: User | null;

     /* data ----------------------------------------------------------- */
     version: string | null;
     users: { users: User[]; total: number };
     inbounds: Inbounds;
     filters: FilterType;
     subscribeUrl: string | null;
     QRcodeLinks: string[] | null;
     loading: boolean;

     /* actions -------------------------------------------------------- */
     onCreateUser: (isOpen: boolean) => void;
     onEditingUser: (u: User | null) => void;
     onDeletingUser: (u: User | null) => void;
     onResetAllUsage: (v: boolean) => void;
     onEditingNodes: (v: boolean) => void;
     onShowingNodesUsage: (v: boolean) => void;
     onResetUsageUser: (u: User | null) => void;
     onRevokeSubscriptionUser: (u: User | null) => void;
     onFilterChange: (p: Partial<FilterType>) => void;
     setQRCode: (links: string[] | null) => void;
     setSubLink: (url: string | null) => void;

     /* server calls --------------------------------------------------- */
     refetchUsers: () => void;
     fetchUserUsage: (u: User, q: FilterUsageType) => Promise<any>;
     fetchAllInbounds: () => Promise<void>;
     resetAllUsage: () => Promise<void>;
     resetDataUsage: (u: User) => Promise<void>;
     resetUserUsage: (account_number: string) => Promise<void>;
     revokeSubscription: (u: User) => Promise<User | void>;
     deleteUser: (u: User) => Promise<void>;
     createUser: (u: UserCreate) => Promise<void>;
     editUser: (u: UserCreate) => Promise<User | void>;
   };

   /* ------------------------------------------------------------------ */
   /* ---------------------- helper (users fetch) ---------------------- */
   /* ------------------------------------------------------------------ */

   const fetchUsers = async (query: FilterType) => {
     const activeQuery: Record<string, unknown> = {};
     (Object.keys(query) as Array<keyof FilterType>).forEach((k) => {
       const v = query[k];
       if (v !== undefined && v !== "") activeQuery[k] = v;
     });

     useDashboard.setState({ loading: true });
     try {
       const resp = await http.get<{ users: User[]; total: number }>(
         "/users",
         { query: activeQuery }
       );
       useDashboard.setState({ users: resp });
       return resp;
     } catch (err) {
       console.error("Failed to fetch users:", err);
       useDashboard.setState({ users: { users: [], total: 0 } });
       return { users: [], total: 0 };
     } finally {
       useDashboard.setState({ loading: false });
     }
   };

   /* ------------------------------------------------------------------ */
   /* -------------------- helper (inbounds fetch) --------------------- */
   /* ------------------------------------------------------------------ */

   export const fetchInbounds = async () => {
     useDashboard.setState({ loading: true });
     try {
       const data = await http.get<Record<ProtocolType, InboundType[]>>(
         "/inbounds"
       );
       useDashboard.setState({
         inbounds: new Map(Object.entries(data)) as Inbounds,
       });
     } catch (err) {
       console.error("Failed to fetch inbounds:", err);
       useDashboard.setState({ inbounds: new Map() });
     } finally {
       useDashboard.setState({ loading: false });
     }
   };

   /* ------------------------------------------------------------------ */
   /* --------------------------- store -------------------------------- */
   /* ------------------------------------------------------------------ */

   export const useDashboard = create(
     subscribeWithSelector<DashboardStateType>((set, get) => ({
       /* ---------- ui-state ----------- */
       isCreatingNewUser: false,
       editingUser: null,
       deletingUser: null,
       isEditingNodes: false,
       isShowingNodesUsage: false,
       isEditingCore: false,
       isResetingAllUsage: false,
       resetUsageUser: null,
       revokeSubscriptionUser: null,

       /* -------------- data ---------- */
       version: null,
       inbounds: new Map(),
       users: { users: [], total: 0 },
       loading: true,
       filters: {
         search: "",
         limit: getUsersPerPageLimitSize(),
         offset: 0,
         sort: "-created_at",
         status: undefined,
       },
       subscribeUrl: null,
       QRcodeLinks: null,

       /* ------------- actions -------- */
       /* simple setters */
       onCreateUser: (v) => set({ isCreatingNewUser: v, editingUser: null }),
       onEditingUser: (u) => set({ editingUser: u, isCreatingNewUser: false }),
       onDeletingUser: (u) => set({ deletingUser: u }),
       onResetAllUsage: (v) => set({ isResetingAllUsage: v }),
       onEditingNodes: (v) => set({ isEditingNodes: v }),
       onShowingNodesUsage: (v) => set({ isShowingNodesUsage: v }),
       onResetUsageUser: (u) => set({ resetUsageUser: u }),
       onRevokeSubscriptionUser: (u) => set({ revokeSubscriptionUser: u }),
       setQRCode: (links) => set({ QRcodeLinks: links }),
       setSubLink: (url) => set({ subscribeUrl: url }),

       onFilterChange: (partial) => {
         const cur = get().filters;
         const next: FilterType = { ...cur, ...partial };

         /* reset offset when list-changing filters change                */
         if (
           partial.search !== undefined ||
           partial.status !== undefined ||
           (partial.limit !== undefined && partial.limit !== cur.limit)
         ) {
           next.offset = 0;
         }

         set({ filters: next });
         get().refetchUsers();
       },

       /* server calls */
       refetchUsers: () => {
         fetchUsers(get().filters);
       },

       fetchAllInbounds: fetchInbounds,

       resetAllUsage: async () => {
         await http.post("/users/reset");
         get().onResetAllUsage(false);
         get().refetchUsers();
       },

       deleteUser: async (user) => {
         const acc = user.account_number?.trim();
         if (!acc) throw new Error("Invalid account number");
         await http.delete(`/user/${acc}`);
         set({ deletingUser: null });
         get().refetchUsers();
         queryClient.invalidateQueries({ queryKey: StatisticsQueryKey });
       },

       createUser: async (body) => {
         await http.post("/user", body);
         set({ isCreatingNewUser: false });
         get().refetchUsers();
         queryClient.invalidateQueries({ queryKey: StatisticsQueryKey });
       },

       editUser: async (body) => {
         const acc = body.account_number?.trim();
         if (!acc) throw new Error("Invalid account number");
         const updated = await http.put<User>(`/user/${acc}`, body);
         set({ editingUser: null });
         get().refetchUsers();
         return updated;
       },

       fetchUserUsage: async (user, q) => {
         const acc = user.account_number?.trim();
         if (!acc) throw new Error("Invalid account number");

         const active: Record<string, unknown> = {};
         (Object.keys(q) as Array<keyof FilterUsageType>).forEach((k) => {
           if (q[k]) active[k] = q[k];
         });
         return http.get(`/user/${acc}/usage`, { query: active });
       },

       resetDataUsage: async (user) => {
         const acc = user.account_number?.trim();
         if (!acc) throw new Error("Invalid account number");
         await http.post(`/user/${acc}/reset`);
         get().refetchUsers();
       },

       resetUserUsage: async (acc) => {
         const clean = acc.trim();
         if (!clean) throw new Error("Invalid account number");
         await http.post(`/user/${clean}/reset`);
         get().refetchUsers();
       },

       revokeSubscription: async (user) => {
         const acc = user.account_number?.trim();
         if (!acc) throw new Error("Invalid account number");
         const res = await http.post<User>(`/user/${acc}/revoke_sub`);
         set({ revokeSubscriptionUser: null });

         /* optimistic update if the API returns the updated user -------- */
         if (res?.account_number) {
           set((s) => ({
             users: {
               ...s.users,
               users: s.users.users.map((u) =>
                 u.account_number === res.account_number ? res : u
               ),
             },
             editingUser:
               s.editingUser?.account_number === res.account_number
                 ? res
                 : s.editingUser,
           }));
         } else {
           get().refetchUsers();
         }
         return res;
       },
     }))
   );
