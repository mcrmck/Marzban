import {
  Box,
  BoxProps,
  Button,
  chakra,
  Grid,
  GridItem,
  HStack,
  IconButton,
  Input,
  Spinner,
} from "@chakra-ui/react";
import {
  ArrowPathIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import classNames from "classnames";
import { useDashboard } from "../../lib/stores/DashboardContext";
import debounce from "lodash.debounce";
import React, { FC, useState } from "react";
import { useTranslation } from "react-i18next";

const SearchIcon = chakra(MagnifyingGlassIcon);
const ClearIcon = chakra(XMarkIcon);
export const ReloadIcon = chakra(ArrowPathIcon);

export type FilterProps = {} & BoxProps;
const setSearchField = debounce((search: string) => {
  useDashboard.getState().onFilterChange({
    ...useDashboard.getState().filters,
    offset: 0,
    search,
  });
}, 300);

export const Filters: FC<FilterProps> = ({ ...props }) => {
  const { loading, filters, onFilterChange, refetchUsers, onCreateUser } =
    useDashboard();
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setSearchField(e.target.value);
  };
  const clear = () => {
    setSearch("");
    onFilterChange({
      ...filters,
      offset: 0,
      search: "",
    });
  };
  return (
    <Grid
      id="filters"
      templateColumns={{
        lg: "repeat(3, 1fr)",
        md: "repeat(4, 1fr)",
        base: "repeat(1, 1fr)",
      }}
      position="sticky"
      top={0}
      mx="-6"
      px="6"
      rowGap={4}
      gap={{
        lg: 4,
        base: 0,
      }}
      bg="var(--chakra-colors-chakra-body-bg)"
      py={4}
      zIndex="docked"
      {...props}
    >
      <GridItem colSpan={{ base: 1, md: 2, lg: 1 }} order={{ base: 2, md: 1 }}>
        <Box position="relative">
          <Input
            placeholder={t("search")}
            value={search}
            borderColor="light-border"
            onChange={onChange}
            paddingLeft="2.5rem"
            paddingRight={filters.search && filters.search.length > 0 ? "2.5rem" : "1rem"}
          />
          <Box
            position="absolute"
            left="0.75rem"
            top="50%"
            transform="translateY(-50%)"
            pointerEvents="none"
          >
            <SearchIcon w={4} h={4} />
          </Box>
          {(loading || (filters.search && filters.search.length > 0)) && (
            <Box
              position="absolute"
              right="0.75rem"
              top="50%"
              transform="translateY(-50%)"
            >
              <HStack>
                {loading && <Spinner size="xs" />}
                {filters.search && filters.search.length > 0 && (
                  <IconButton
                    onClick={clear}
                    aria-label="clear"
                    size="xs"
                    variant="ghost"
                  >
                    <ClearIcon w={4} h={4} />
                  </IconButton>
                )}
              </HStack>
            </Box>
          )}
        </Box>
      </GridItem>
      <GridItem colSpan={2} order={{ base: 1, md: 2 }}>
        <HStack justifyContent="flex-end" alignItems="center" h="full">
          <IconButton
            aria-label="refresh users"
            disabled={loading}
            onClick={refetchUsers}
            size="sm"
            variant="outline"
          >
            <ReloadIcon
              className={classNames({
                "animate-spin": loading,
              })}
            />
          </IconButton>
          <Button
            colorScheme="primary"
            size="sm"
            onClick={() => onCreateUser(true)}
            px={5}
          >
            {t("createUser")}
          </Button>
        </HStack>
      </GridItem>
    </Grid>
  );
};
