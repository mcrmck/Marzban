const CLIENT_AUTH_TOKEN_KEY = "clientAuthToken";

export const getClientAuthToken = (): string | null => {
    return localStorage.getItem(CLIENT_AUTH_TOKEN_KEY);
};

export const saveClientAuthToken = (token: string): void => {
    localStorage.setItem(CLIENT_AUTH_TOKEN_KEY, token);
};

export const removeClientAuthToken = (): void => {
    localStorage.removeItem(CLIENT_AUTH_TOKEN_KEY);
};