const ADMIN_TOKEN_KEY = "admin_token";

export const getToken = (): string | null => {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  console.debug('AuthStorage: Raw token from localStorage:', token);
  
  // Handle cases where token is stored as string "null" or "undefined"
  if (!token || token === 'null' || token === 'undefined' || token.trim() === '') {
    console.debug('AuthStorage: No valid token found, removing invalid token');
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    return null;
  }
  
  console.debug('AuthStorage: Retrieved valid token from localStorage:', token.substring(0, 20) + '...');
  return token;
};

export const setToken = (token: string): void => {
  console.debug('AuthStorage: Setting token:', token?.substring(0, 20) + '...');
  
  if (!token || token === 'null' || token === 'undefined' || token.trim() === '') {
    console.error('AuthStorage: Attempted to store invalid token:', token);
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    return;
  }
  
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
  console.debug('AuthStorage: Token stored successfully');
};

export const removeToken = (): void => {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
};

// Legacy aliases for backward compatibility
export const getAuthToken = getToken;
export const setAuthToken = setToken;
export const removeAuthToken = removeToken;
