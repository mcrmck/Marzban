import {
  Box,
  Button,
  Container,
  Flex,
  Heading,
  Stack,
  Text,
  useColorModeValue,
  VStack,
  HStack,
  Icon,
} from "@chakra-ui/react";
import { useNavigate } from "react-router-dom";
import { FaShieldAlt, FaGlobe, FaLock } from "react-icons/fa";

const Feature = ({ icon, title, text }: { icon: any; title: string; text: string }) => {
  return (
    <Stack spacing={4} align="center" textAlign="center">
      <Flex
        w={16}
        h={16}
        align="center"
        justify="center"
        color="white"
        rounded="full"
        bg={useColorModeValue("blue.500", "blue.300")}
        mb={1}
      >
        <Icon as={icon} w={8} h={8} />
      </Flex>
      <Text fontWeight={600}>{title}</Text>
      <Text color={useColorModeValue("gray.600", "gray.400")}>{text}</Text>
    </Stack>
  );
};

export const ClientLandingPage = () => {
  const navigate = useNavigate();
  const bgColor = useColorModeValue("white", "gray.800");
  const textColor = useColorModeValue("gray.600", "gray.400");

  return (
    <Box>
      {/* Navigation Bar */}
      <Box
        position="fixed"
        top={0}
        left={0}
        right={0}
        bg={bgColor}
        boxShadow="sm"
        zIndex={1000}
      >
        <Container maxW="container.xl">
          <Flex h={16} alignItems="center" justifyContent="space-between">
            <Heading size="md">Marzban VPN</Heading>
            <HStack spacing={4}>
              <Button variant="ghost" onClick={() => navigate("/login")}>
                Login
              </Button>
              <Button variant="ghost" onClick={() => navigate("/register")}>
                Register
              </Button>
              <Button colorScheme="blue" onClick={() => navigate("/plans")}>
                Get Started
              </Button>
            </HStack>
          </Flex>
        </Container>
      </Box>

      {/* Hero Section */}
      <Box pt={24} pb={20}>
        <Container maxW="container.xl">
          <Stack spacing={8} align="center" textAlign="center">
            <Heading
              fontSize={{ base: "3xl", md: "4xl", lg: "5xl" }}
              bgGradient="linear(to-r, blue.400, blue.600)"
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
              colorScheme="blue"
              onClick={() => navigate("/plans")}
            >
              View Plans
            </Button>
          </Stack>
        </Container>
      </Box>

      {/* Features Section */}
      <Box py={20} bg={useColorModeValue("gray.50", "gray.900")}>
        <Container maxW="container.xl">
          <VStack spacing={12}>
            <Heading textAlign="center">Why Choose Our VPN?</Heading>
            <Stack
              direction={{ base: "column", md: "row" }}
              spacing={10}
              align="center"
            >
              <Feature
                icon={FaShieldAlt}
                title="Strong Security"
                text="Military-grade encryption to keep your data safe and secure"
              />
              <Feature
                icon={FaGlobe}
                title="Global Access"
                text="Access content from anywhere with our worldwide server network"
              />
              <Feature
                icon={FaLock}
                title="Privacy First"
                text="No logs policy ensures your online activities remain private"
              />
            </Stack>
          </VStack>
        </Container>
      </Box>
    </Box>
  );
};