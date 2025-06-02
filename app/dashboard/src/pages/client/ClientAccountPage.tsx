import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    Container,
    Grid,
    Heading,
    Text,
    VStack,
    HStack,
    Badge,
    Divider,
    useToast,
    Spinner,
    Card,
    CardBody,
    CardHeader,
    Stat,
    StatLabel,
    StatNumber,
    StatHelpText,
    IconButton,
    useClipboard,
} from "@chakra-ui/react";
import { useClientPortalStore } from "../../store/clientPortalStore";
import { QRCodeSVG } from "qrcode.react";
import type { ClientNode } from "../../types/clientPortal";
import { CheckIcon, CopyIcon } from "@chakra-ui/icons";

const AccountContent = ({ user, active_node, available_nodes = [] }: {
    user: any,
    active_node: any,
    available_nodes: ClientNode[]
}) => {
    const navigate = useNavigate();
    const toast = useToast();
    const { logout } = useClientPortalStore();
    const { hasCopied, onCopy } = useClipboard(user.account_number);

    const handleLogout = () => {
        logout();
        navigate("/portal/login");
    };

    const handleCopyAccountNumber = () => {
        onCopy();
        toast({
            title: "Copied!",
            description: "Account number copied to clipboard",
            status: "success",
            duration: 2000,
            isClosable: true,
        });
    };

    return (
        <Container maxW="container.xl" py={10}>
            <VStack spacing={8} align="stretch">
                <HStack justify="space-between">
                    <Box>
                        <Heading size="xl">Account Dashboard</Heading>
                        <Text color="gray.600">Welcome back!</Text>
                    </Box>
                    <Button colorScheme="red" onClick={handleLogout}>
                        Logout
                    </Button>
                </HStack>

                <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }} gap={6}>
                    {/* Account Status Card */}
                    <Card>
                        <CardHeader>
                            <Heading size="md">Account Status</Heading>
                        </CardHeader>
                        <CardBody>
                            <VStack spacing={4} align="stretch">
                                <Stat>
                                    <StatLabel>Account Number</StatLabel>
                                    <HStack>
                                        <StatNumber fontSize="md" fontFamily="mono">
                                            {user.account_number}
                                        </StatNumber>
                                        <IconButton
                                            aria-label="Copy account number"
                                            icon={hasCopied ? <CheckIcon /> : <CopyIcon />}
                                            onClick={handleCopyAccountNumber}
                                            size="sm"
                                            colorScheme={hasCopied ? "green" : "gray"}
                                        />
                                    </HStack>
                                    <StatHelpText>Use this number to log in</StatHelpText>
                                </Stat>
                                <Stat>
                                    <StatLabel>Status</StatLabel>
                                    <StatNumber>
                                        <Badge
                                            colorScheme={user.status === "active" ? "green" : "red"}
                                            fontSize="md"
                                        >
                                            {user.status}
                                        </Badge>
                                    </StatNumber>
                                </Stat>
                                <Stat>
                                    <StatLabel>Data Limit</StatLabel>
                                    <StatNumber>{user.data_limit || "Unlimited"}</StatNumber>
                                </Stat>
                                <Stat>
                                    <StatLabel>Expiry Date</StatLabel>
                                    <StatNumber>{user.expire}</StatNumber>
                                </Stat>
                            </VStack>
                        </CardBody>
                    </Card>

                    {/* Active Node Card */}
                    <Card>
                        <CardHeader>
                            <Heading size="md">Active Node</Heading>
                        </CardHeader>
                        <CardBody>
                            {active_node ? (
                                <VStack spacing={4} align="stretch">
                                    <Text fontWeight="bold">{active_node.name}</Text>
                                    <Text>{active_node.address}</Text>
                                    <Text color="gray.600">{active_node.location}</Text>
                                </VStack>
                            ) : (
                                <Text color="gray.500">No active node selected</Text>
                            )}
                        </CardBody>
                    </Card>
                </Grid>

                {/* Subscription Link and QR Codes */}
                <Card>
                    <CardHeader>
                        <Heading size="md">Connection Details</Heading>
                    </CardHeader>
                    <CardBody>
                        <VStack spacing={6}>
                            <Box width="full">
                                <Text fontWeight="bold" mb={2}>Subscription Link</Text>
                                <Text
                                    p={2}
                                    bg="gray.50"
                                    borderRadius="md"
                                    fontFamily="mono"
                                    fontSize="sm"
                                >
                                    {user.sub_link}
                                </Text>
                            </Box>

                            {user.qr_code_url_list?.length > 0 && (
                                <>
                                    <Divider />
                                    <Box>
                                        <Text fontWeight="bold" mb={4}>QR Codes</Text>
                                        <Grid
                                            templateColumns={{
                                                base: "1fr",
                                                md: "repeat(2, 1fr)",
                                                lg: "repeat(3, 1fr)",
                                            }}
                                            gap={4}
                                        >
                                            {user.qr_code_url_list.map((url: string, index: number) => (
                                                <Box
                                                    key={index}
                                                    p={4}
                                                    borderWidth="1px"
                                                    borderRadius="md"
                                                    textAlign="center"
                                                >
                                                    <QRCodeSVG value={url} size={200} />
                                                </Box>
                                            ))}
                                        </Grid>
                                    </Box>
                                </>
                            )}
                        </VStack>
                    </CardBody>
                </Card>

                {/* Available Nodes */}
                {available_nodes.length > 0 && (
                    <Card>
                        <CardHeader>
                            <Heading size="md">Available Nodes</Heading>
                        </CardHeader>
                        <CardBody>
                            <Grid
                                templateColumns={{
                                    base: "1fr",
                                    md: "repeat(2, 1fr)",
                                    lg: "repeat(3, 1fr)",
                                }}
                                gap={4}
                            >
                                {available_nodes.map((node: ClientNode) => (
                                    <Box
                                        key={node.id}
                                        p={4}
                                        borderWidth="1px"
                                        borderRadius="md"
                                    >
                                        <VStack align="stretch" spacing={2}>
                                            <Text fontWeight="bold">{node.name}</Text>
                                            <Text fontSize="sm">{node.address}</Text>
                                            <Text fontSize="sm" color="gray.600">
                                                {node.location}
                                            </Text>
                                        </VStack>
                                    </Box>
                                ))}
                            </Grid>
                        </CardBody>
                    </Card>
                )}
            </VStack>
        </Container>
    );
};

export const ClientAccountPage = () => {
    const { clientDetails, fetchClientDetails, isLoadingDetails } = useClientPortalStore();

    useEffect(() => {
        fetchClientDetails();
    }, [fetchClientDetails]);

    if (isLoadingDetails) {
        return (
            <Container centerContent py={10}>
                <Spinner size="xl" />
            </Container>
        );
    }

    if (!clientDetails) {
        return (
            <Container centerContent py={10}>
                <Text>No client details available</Text>
            </Container>
        );
    }

    return <AccountContent {...clientDetails} />;
};