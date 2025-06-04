import { useNavigate } from "react-router-dom";
import {
    Box,
    Button,
    Container,
    Heading,
    Text,
    Stack,
    Icon,
} from "@chakra-ui/react";
import { useColorMode } from "@chakra-ui/color-mode";
import { FaShieldAlt, FaGlobe, FaLock } from "react-icons/fa";

const Feature = ({ icon, title, text }: { icon: any; title: string; text: string }) => {
    return (
        <Box textAlign="center">
            <Icon
                as={icon}
                w="3rem"
                h="3rem"
                color="brand.500"
                mb={4}
                mx="auto"
            />
            <Heading size="md" mb={2}>
                {title}
            </Heading>
            <Text color="gray.600">{text}</Text>
        </Box>
    );
};

const ClientLandingPage = () => {
  const navigate = useNavigate();
  const { colorMode } = useColorMode();
  const textColor = colorMode === "light" ? "gray.600" : "gray.400";

  return (
    <Box>
      {/* Hero Section */}
      <Box pt={24} pb={20}>
        <Container maxW="container.xl">
          <Stack gap={8} align="center" textAlign="center">
            <Heading
              fontSize={{ base: "3xl", md: "4xl", lg: "5xl" }}
              bgGradient="linear(to-r, brand.400, brand.600)"
              bgClip="text"
            >
              Secure, Fast, and Private VPN Service
            </Heading>
            <Text fontSize="xl" color={textColor} maxW="2xl">
              Experience unrestricted internet access with our premium VPN service.
              Protect your privacy and bypass geo-restrictions with ease.
            </Text>
            <Button
              size="lg"
              colorScheme="brand"
              onClick={() => navigate("/plans")}
            >
              View Plans
            </Button>
          </Stack>
        </Container>
      </Box>

      {/* Features Section */}
      <Box py={20} bg="gray.50" _dark={{ bg: "gray.800" }}>
        <Container maxW="container.xl">
          <Stack gap={12}>
            <Box textAlign="center">
              <Heading size="xl" mb={4}>
                Why Choose Our Service?
              </Heading>
              <Text fontSize="lg" color={textColor} maxW="2xl" mx="auto">
                Experience the best VPN service with our premium features
              </Text>
            </Box>

            <Stack
              direction={{ base: "column", md: "row" }}
              gap={8}
              align="center"
            >
              <Feature
                icon={FaShieldAlt}
                title="Enhanced Security"
                text="Military-grade encryption to protect your online activities"
              />
              <Feature
                icon={FaGlobe}
                title="Global Access"
                text="Access content from anywhere with our worldwide server network"
              />
              <Feature
                icon={FaLock}
                title="Privacy First"
                text="Your data is yours - we don't log or track your activities"
              />
            </Stack>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
};

export default ClientLandingPage;