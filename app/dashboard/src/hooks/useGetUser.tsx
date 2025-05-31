import { fetch } from "service/http";
import { UserApi, UseGetUserReturn } from "types/User"; // UserApi is the revised one
import { useQuery } from "react-query";

export const useGetUser = (): UseGetUserReturn => {
    const {
        data: userData,
        isLoading: getUserIsPending,
        isSuccess: getUserIsSuccess,
        isError: getUserIsError,
        error: queryError, // queryError will be 'Error | null'
    } = useQuery<UserApi, Error>(["user"], async () => { // TData is UserApi, TError is Error
        const data = await fetch("/admin"); // fetch returns parsed JSON

        // Map to the revised UserApi structure
        return {
            username: data.username,
            is_sudo: data.is_sudo !== undefined ? data.is_sudo : false,
            users_usage: data.users_usage,
            telegram_id: data.telegram_id ?? null, // Handle undefined from fetch if API omits optional fields
            discord_webhook: data.discord_webhook ?? null, // Handle undefined
        };
    });

    return {
        userData, // userData is now UserApi | undefined
        getUserIsPending,
        getUserIsSuccess,
        getUserIsError,
        getUserError: queryError || null, // Ensures Error | null
    };
};

export default useGetUser;