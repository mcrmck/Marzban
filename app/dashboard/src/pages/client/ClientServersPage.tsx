import { useEffect } from "react";
import {
    Box,
    Container,
    Heading,
    Text,
    VStack,
    Table,
    Thead,
    Tbody,
    Tr,
    Th,
    Td,
    Badge,
    Spinner,
    useToast,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../store/clientPortalStore";
import type { ClientNode } from "../../types/clientPortal";

export const ClientServersPage = () => {
    const toast = useToast();
    const { servers, fetchServers, isLoadingServers } = useClientPortalStore();

    useEffect(() => {
        fetchServers().catch((error) => {
            toast({
                title: "Error",
                description: "Failed to fetch servers. Please try again.",
                status: "error",
                duration: 5000,
                isClosable: true,
            });
        });
    }, [fetchServers, toast]);

    if (isLoadingServers) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    return (
        <Container maxW="container.xl" py={10}>
            <VStack spacing={8} align="stretch">
                <Box>
                    <Heading size="xl">Available Servers</Heading>
                    <Text color="gray.600" mt={2}>
                        List of all available servers for your account
                    </Text>
                </Box>

                <Box overflowX="auto">
                    <Table variant="simple">
                        <Thead>
                            <Tr>
                                <Th>Name</Th>
                                <Th>Location</Th>
                                <Th>Address</Th>
                                <Th>Status</Th>
                            </Tr>
                        </Thead>
                        <Tbody>
                            {servers.map((server: ClientNode) => (
                                <Tr key={server.id}>
                                    <Td fontWeight="medium">{server.name}</Td>
                                    <Td>{server.location}</Td>
                                    <Td fontFamily="mono" fontSize="sm">
                                        {server.address}
                                    </Td>
                                    <Td>
                                        <Badge
                                            colorScheme={
                                                server.status === "online"
                                                    ? "green"
                                                    : "red"
                                            }
                                        >
                                            {server.status}
                                        </Badge>
                                    </Td>
                                </Tr>
                            ))}
                        </Tbody>
                    </Table>
                </Box>
            </VStack>
        </Container>
    );
};