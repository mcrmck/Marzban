/**
 * Global providers wrapper
 * Consolidates all app-level providers for both admin and client
 */

import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChakraProvider } from "@chakra-ui/react";

// Theme imports
import adminTheme from "../../theme/adminTheme";
import clientTheme from "../../theme/clientTheme";

interface GlobalProvidersProps {
  children: ReactNode;
  mode?: "admin" | "client";
}

// Create query client instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

export const GlobalProviders = ({ children, mode = "admin" }: GlobalProvidersProps) => {
  const theme = mode === "admin" ? adminTheme : clientTheme;

  return (
    <ChakraProvider value={theme}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ChakraProvider>
  );
};