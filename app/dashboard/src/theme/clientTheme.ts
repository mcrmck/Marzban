import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

const colors = {
  brand: {
    50: '#f0fdf4',
    100: '#dcfce7',
    200: '#bbf7d0',
    300: '#86efac',
    400: '#4ade80',
    500: '#22c55e', // Primary brand color
    600: '#16a34a',
    700: '#15803d',
    800: '#166534',
    900: '#14532d',
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

export const clientTheme = extendTheme({
  config,
  colors,
  components,
  styles,
});