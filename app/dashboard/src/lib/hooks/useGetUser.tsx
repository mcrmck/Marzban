import { useQuery } from "@tanstack/react-query";
import { fetch } from "../api";
import { UserApi } from "../types";
import { useClientPortalStore } from "../stores";

export const useGetUser = () => {
    const {  } = useClientPortalStore();

    return useQuery({
        queryKey: ['user'],
        queryFn: () => fetch.get<UserApi>('/api/user'),
    });
};

export default useGetUser;