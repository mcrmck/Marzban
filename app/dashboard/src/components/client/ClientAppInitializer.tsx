import { FC, useEffect } from "react";
import { useClientPortalStore } from "../../lib/stores";

export const ClientAppInitializer: FC = () => {
    const initializeAuth = useClientPortalStore(state => state.initializeAuth);

    useEffect(() => {
        initializeAuth();
    }, [initializeAuth]);

    return null;
};