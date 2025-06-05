import { useEffect } from "react";
import {
    Box,
    Container,
    Heading,
    Text,
    VStack,
    Table,
    Badge,
    Spinner,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../lib/stores";
import type { ClientNode } from "../../lib/types";
import { toaster } from "../../components/shared/ui/toaster";

export const ClientServersPage = () => {
    const { servers, fetchServers, isLoadingServers } = useClientPortalStore();

    useEffect(() => {
        fetchServers().catch(() => {
            toaster.create({
                title: "Error",
                description: "Failed to fetch servers. Please try again.",
                type: "error",
                duration: 5000,
                closable: true,
            });
        });
    }, [fetchServers]);

    if (isLoadingServers) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    return (
        <Container maxW="container.xl" py={10}>
            <VStack gap={8} align="stretch">
                <Box>
                    <Heading size="xl">Available Servers</Heading>
                    <Text color="gray.600" mt={2}>
                        List of all available servers for your account
                    </Text>
                </Box>

                <Box overflowX="auto">
                    <Table.Root>
                        <Table.Header>
                            <Table.Row>
                                <Table.ColumnHeader>Name</Table.ColumnHeader>
                                <Table.ColumnHeader>Location</Table.ColumnHeader>
                                <Table.ColumnHeader>Address</Table.ColumnHeader>
                                <Table.ColumnHeader>Status</Table.ColumnHeader>
                            </Table.Row>
                        </Table.Header>
                        <Table.Body>
                            {servers.map((server: ClientNode) => (
                                <Table.Row key={server.id}>
                                    <Table.Cell fontWeight="medium">{server.name}</Table.Cell>
                                    <Table.Cell>{server.location}</Table.Cell>
                                    <Table.Cell fontFamily="mono" fontSize="sm">
                                        {server.address}
                                    </Table.Cell>
                                    <Table.Cell>
                                        <Badge
                                            colorScheme={
                                                server.status === "online"
                                                    ? "green"
                                                    : "red"
                                            }
                                        >
                                            {server.status}
                                        </Badge>
                                    </Table.Cell>
                                </Table.Row>
                            ))}
                        </Table.Body>
                    </Table.Root>
                </Box>
            </VStack>
        </Container>
    );
};