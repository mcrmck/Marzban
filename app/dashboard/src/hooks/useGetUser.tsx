import { fetch } from "service/http";
import { UserApi, UseGetUserReturn } from "types/User";
import { useQuery } from "react-query";
import { useClientPortalStore } from "store/clientPortalStore";

export const useGetUser = (): UseGetUserReturn => {
    const { clientDetails } = useClientPortalStore();

    const {
        data: userData,
        isLoading: getUserIsPending,
        isSuccess: getUserIsSuccess,
        isError: getUserIsError,
        error: queryError,
    } = useQuery<UserApi, Error>(["user"], async () => {
        if (!clientDetails) {
            throw new Error("No client details available");
        }

        return {
            username: clientDetails.user.username,
            is_sudo: false,
            users_usage: clientDetails.user.xray_user?.used_traffic || 0,
            telegram_id: null,
            discord_webhook: null,
        };
    }, {
        enabled: !!clientDetails,
    });

    return {
        userData,
        getUserIsPending,
        getUserIsSuccess,
        getUserIsError,
        getUserError: queryError || null,
    };
};

export default useGetUser;