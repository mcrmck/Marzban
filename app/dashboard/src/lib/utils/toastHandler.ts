/**
 * Toast utilities for Chakra UI v3
 * Provides standardized toast notifications with proper theming
 */

import { toaster } from "../../components/shared/ui/toaster";

export type ToastStatus = "success" | "error" | "warning" | "info" | "loading";

export interface ToastOptions {
  title?: string;
  description?: string;
  status?: ToastStatus;
  duration?: number;
  closable?: boolean;
  position?: "top" | "top-start" | "top-end" | "bottom" | "bottom-start" | "bottom-end";
}

/**
 * Show a standardized toast notification
 */
export const showToast = (options: ToastOptions) => {
  const {
    title,
    description,
    status = "info",
    duration = 5000,
    closable = true,
    position = "top-end",
  } = options;

  return toaster.create({
    title,
    description,
    type: status as any,
    duration,
    closable,
  });
};

/**
 * Success toast shorthand
 */
export const showSuccessToast = (title: string, description?: string) => {
  return showToast({
    title,
    description,
    status: "success",
  });
};

/**
 * Error toast shorthand
 */
export const showErrorToast = (title: string, description?: string) => {
  return showToast({
    title,
    description,
    status: "error",
    duration: 7000, // Longer duration for errors
  });
};

/**
 * Warning toast shorthand
 */
export const showWarningToast = (title: string, description?: string) => {
  return showToast({
    title,
    description,
    status: "warning",
  });
};

/**
 * Info toast shorthand
 */
export const showInfoToast = (title: string, description?: string) => {
  return showToast({
    title,
    description,
    status: "info",
  });
};

/**
 * Loading toast shorthand
 */
export const showLoadingToast = (title: string, description?: string) => {
  return showToast({
    title,
    description,
    status: "loading",
    duration: undefined, // Loading toasts don't auto-dismiss
    closable: false,
  });
};

/**
 * Close all toasts
 */
export const closeAllToasts = () => {
  toaster.dismiss();
};

/**
 * Close specific toast by ID
 */
export const closeToast = (id: string) => {
  toaster.dismiss(id);
};

/**
 * Toast with custom configuration
 */
export const createCustomToast = (options: Parameters<typeof toaster.create>[0]) => {
  return toaster.create(options);
};

/**
 * Legacy toast handler interface for backward compatibility
 */
export const toast = {
  success: showSuccessToast,
  error: showErrorToast,
  warning: showWarningToast,
  info: showInfoToast,
  loading: showLoadingToast,
  dismiss: closeAllToasts,
  dismissById: closeToast,
};

export default toast;