/**
 * Consolidated UI components export
 * All UI primitives with Chakra UI v3 compatibility
 */


// Re-export Chakra components that work as-is in v3
export {
  Box,
  Flex,
  Stack,
  HStack,
  VStack,
  Grid,
  GridItem,
  Container,
  Spacer,
  Card,
  Text,
  Heading,
  Link,
  Image,
  Icon,
  Spinner,
  Badge,
  Tag,
  Avatar,
  Tooltip,
  Popover,
  Drawer,
  Menu,
  Switch,
  Checkbox,
  RadioGroup,
  Textarea,
  NumberInput,
  PinInput,
  Slider,
  Progress,
  Skeleton,
  Alert,
  CloseButton,
  ButtonGroup,
  Tabs,
  Table,
  Field,
  Accordion
} from "@chakra-ui/react";

// Color mode utilities
export { useColorMode, ColorModeProvider, type ColorMode } from "../../../lib/theme/colorMode";
