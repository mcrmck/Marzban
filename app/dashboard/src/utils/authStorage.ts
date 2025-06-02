const CLIENT_TOKEN_KEY = "client_token";

export const getAuthToken = (): string | null => {
  return localStorage.getItem(CLIENT_TOKEN_KEY);
};

export const setAuthToken = (token: string): void => {
  localStorage.setItem(CLIENT_TOKEN_KEY, token);
};

export const removeAuthToken = (): void => {
  localStorage.removeItem(CLIENT_TOKEN_KEY);
};
