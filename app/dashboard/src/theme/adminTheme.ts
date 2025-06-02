import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

const colors = {
  brand: {
    50: '#f0f9ff',
    100: '#e0f2fe',
    200: '#bae6fd',
    300: '#7dd3fc',
    400: '#38bdf8',
    500: '#0ea5e9', // Primary brand color
    600: '#0284c7',
    700: '#0369a1',
    800: '#075985',
    900: '#0c4a6e',
  },
};

const components = {
  Button: {
    defaultProps: {
      colorScheme: 'brand',
    },
  },
  Badge: {
    defaultProps: {
      colorScheme: 'brand',
    },
  },
  Link: {
    baseStyle: {
      color: 'brand.500',
      _hover: {
        textDecoration: 'none',
        color: 'brand.600',
      },
    },
  },
};

const styles = {
  global: (props: { colorMode: string }) => ({
    body: {
      bg: props.colorMode === 'dark' ? 'gray.900' : 'gray.50',
      color: props.colorMode === 'dark' ? 'white' : 'gray.800',
    },
  }),
};

export const adminTheme = extendTheme({
  config,
  colors,
  components,
  styles,
});