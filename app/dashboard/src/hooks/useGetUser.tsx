import { getAuthToken } from "utils/authStorage";
import { fetch } from "service/http";
import { UserApi, UseGetUserReturn } from "types/User"; // Make sure UserApi and UseGetUserReturn are correctly defined in types/User.ts
import { useQuery } from "react-query"; // Changed from @tanstack/react-query

// This function seems unused in the hook's current implementation.
// const fetchUser = async () => {
//     return await fetch("/admin");
// }

export const useGetUser = (): UseGetUserReturn => {
    const { data: userData, isLoading: isPending, isSuccess, isError, error } = useQuery({
        queryKey: ["user"], // Query key for the current user's data
        queryFn: async () => {
            // This endpoint should return data matching the UserApi structure or a compatible one.
            const response = await fetch("/user");
            const data = await response.json();
            // Ensure the structure returned by API matches UserApi or cast appropriately.
            // The example mapping below assumes `data` contains these fields.
            // If `is_sudo` is not part of `/user` response, UserApi or this mapping needs adjustment.
            return {
                discord_webhook: data.discord_webhook, // Assuming UserApi uses discord_webhook (corrected typo)
                is_sudo: data.is_sudo !== undefined ? data.is_sudo : false, // Prefer dynamic value if available
                telegram_id: data.telegram_id,
                account_number: data.account_number,
            };
        },
        // Add other react-query options if needed, e.g., staleTime, cacheTime
    });

    return {
        userData: userData as UserApi, // Cast to UserApi; ensure the fetched data structure is compatible.
        getUserIsPending: isPending,
        getUserIsSuccess: isSuccess,
        getUserIsError: isError,
        getUserError: error as Error | null, // Cast error to Error type
    };
};

export default useGetUser;