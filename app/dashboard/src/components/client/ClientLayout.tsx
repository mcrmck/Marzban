import { Box, Container } from "@chakra-ui/react";
import { FC, ReactNode } from "react";
import { ClientHeader } from "./ClientHeader";

interface ClientLayoutProps {
  children: ReactNode;
}

export const ClientLayout: FC<ClientLayoutProps> = ({ children }) => {
  return (
    <Box minH="100vh" bg="gray.50">
      <ClientHeader />
      <Container maxW="container.xl" py={8}>
        {children}
      </Container>
    </Box>
  );
};