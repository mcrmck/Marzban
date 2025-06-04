const ADMIN_TOKEN_KEY = "admin_token";

export const getToken = (): string | null => {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
};

export const setToken = (token: string): void => {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
};

export const removeToken = (): void => {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
};

// Legacy aliases for backward compatibility
export const getAuthToken = getToken;
export const setAuthToken = setToken;
export const removeAuthToken = removeToken;
