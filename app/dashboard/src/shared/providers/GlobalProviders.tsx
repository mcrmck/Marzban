/**
 * Global providers wrapper
 * Consolidates all app-level providers for both admin and client
 */

import { ReactNode, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChakraProvider, Spinner, Box } from "@chakra-ui/react";
import { ColorModeProvider } from "../../lib/theme/colorMode";

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

// Loading component for Suspense
const I18nLoading = () => (
  <Box
    height="100vh"
    display="flex"
    alignItems="center"
    justifyContent="center"
  >
    <Spinner size="xl" color="jade.solid" />
  </Box>
);

export const GlobalProviders = ({ children, mode = "admin" }: GlobalProvidersProps) => {
  const theme = mode === "admin" ? adminTheme : clientTheme;

  return (
    <ColorModeProvider 
      attribute="class" 
      defaultTheme="system" 
      enableSystem
      disableTransitionOnChange={false}
    >
      <ChakraProvider value={theme}>
        <QueryClientProvider client={queryClient}>
          <Suspense fallback={<I18nLoading />}>
            {children}
          </Suspense>
        </QueryClientProvider>
      </ChakraProvider>
    </ColorModeProvider>
  );
};