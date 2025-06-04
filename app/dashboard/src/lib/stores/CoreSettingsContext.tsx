import { fetch } from "../api/http";
import { create } from "zustand";

interface CoreInfo {
  version: string;
  started: boolean;
  logs_websocket: string;
}

type CoreSettingsStore = {
  isLoading: boolean;
  isPostLoading: boolean;
  fetchCoreSettings: () => void;
  updateConfig: (json: string) => Promise<void>;
  restartCore: () => Promise<void>;
  version: string | null;
  started: boolean | null;
  logs_websocket: string | null;
  config: string;
};

export const useCoreSettings = create<CoreSettingsStore>((set) => ({
  isLoading: true,
  isPostLoading: false,
  version: null,
  started: false,
  logs_websocket: null,
  config: "",
  fetchCoreSettings: () => {
    set({ isLoading: true });
    Promise.all([
      fetch.get<CoreInfo>("/core").then(({ version, started, logs_websocket }) =>
        set({ version, started, logs_websocket })
      ),
      fetch.get<string>("/core/config").then((config) => set({ config })),
    ]).finally(() => set({ isLoading: false }));
  },
  updateConfig: (body) => {
    set({ isPostLoading: true });
    return fetch.put("/core/config", body).then(() => {
      set({ isPostLoading: false });
    });
  },
  restartCore: () => {
    return fetch.post("/core/restart");
  },
}));
