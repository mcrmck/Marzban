import { Box, Container } from "@chakra-ui/react";
import { FC, ReactNode } from "react";
import { ClientHeader } from "./ClientHeader";
import { useTheme } from "next-themes";

interface ClientLayoutProps {
  children: ReactNode;
}

export const ClientLayout: FC<ClientLayoutProps> = ({ children }) => {
  const { theme } = useTheme();

  return (
    <Box minH="100vh" bg="bg.canvas">
      <ClientHeader />
      <Container maxW="container.xl" py={8} mt="16">
        {children}
      </Container>
    </Box>
  );
};