// Re-export everything from clientAuthStorage with renamed functions
export { getToken as getClientToken, setToken as setClientToken, removeToken as removeClientToken } from './clientAuthStorage';

// Re-export everything from authStorage with renamed functions
export { getToken as getAdminToken, setToken as setAdminToken, removeToken as removeAdminToken } from './authStorage';

// Re-export everything else
export * from './toastHandler';
export * from './color';
export * from './dateFormatter';
export * from './formatByte';
export * from './logger';
export * from './react-query';
export * from './userPreferenceStorage';
export * from './themeColor';
export * from './format';
export * from './validation';