const CLIENT_AUTH_TOKEN_KEY = "clientAuthToken";

export const getToken = (): string | null => {
    return localStorage.getItem(CLIENT_AUTH_TOKEN_KEY);
};

export const setToken = (token: string): void => {
    localStorage.setItem(CLIENT_AUTH_TOKEN_KEY, token);
};

export const removeToken = (): void => {
    localStorage.removeItem(CLIENT_AUTH_TOKEN_KEY);
};

// Legacy aliases for backward compatibility
export const getClientAuthToken = getToken;
export const saveClientAuthToken = setToken;
export const removeClientAuthToken = removeToken;