/* ----------------------------------------------------------------------
 * Pagination.tsx – Chakra UI v3 (<Pagination>)
 * ------------------------------------------------------------------- */

import {
  Box,
  ButtonGroup,
  HStack,
  IconButton,
  Pagination,
  Select,
  Text,
  chakra,
  createListCollection,
} from "@chakra-ui/react";
import {
  ArrowLongLeftIcon,
  ArrowLongRightIcon,
} from "@heroicons/react/24/outline";
import { ChangeEvent, FC } from "react";
import { useTranslation } from "react-i18next";

import { useDashboard } from "../../lib/stores/DashboardContext";
import { setUsersPerPageLimitSize } from "../../lib/utils/userPreferenceStorage";

/* simple chakra-wrapped icons (style them where they're used) */
const PrevIcon = chakra(ArrowLongLeftIcon);
const NextIcon = chakra(ArrowLongRightIcon);

export const PaginationWidget: FC = () => {
  const {
    filters,
    onFilterChange,
    users: { total },
  } = useDashboard();
  const { t } = useTranslation();

  /* paging maths ------------------------------------------------------- */
  const pageSize  = filters.limit  ?? 10;
  const pageIndex = (filters.offset ?? 0) / pageSize;      // 0-based
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  /* handlers ----------------------------------------------------------- */
  const goToPage = (page: number) =>
    onFilterChange({ ...filters, offset: page * pageSize });

  const handlePageSizeChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const next = Number(e.target.value);
    setUsersPerPageLimitSize(String(next));
    onFilterChange({ ...filters, limit: next, offset: 0 });
  };

  const pageSizeCollection = createListCollection({
    items: [10, 20, 30].map(v => ({ value: String(v), label: String(v) }))
  });

  /* render ------------------------------------------------------------- */
  return (
    <HStack
      mt={4}
      w="full"
      justify="space-between"
      gap={{ base: 4, md: 0 }}
      flexDir={{ base: "column", md: "row" }}
    >
      {/* ─────────── Items-per-page selector ─────────── */}
      <Box order={{ base: 2, md: 1 }}>
        <HStack>
          <Select.Root
            value={[String(pageSize)]}
            onValueChange={(details) => handlePageSizeChange({ target: { value: details.value[0] } } as any)}
            collection={pageSizeCollection}
          >
            <Select.Trigger minW="60px" rounded="md" />
            <Select.Positioner>
              <Select.Content>
                {pageSizeCollection.items.map((item) => (
                  <Select.Item key={item.value} item={item}>
                    {item.label}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Positioner>
          </Select.Root>
          <Text fontSize="sm" whiteSpace="nowrap">
            {t("itemsPerPage")}
          </Text>
        </HStack>
      </Box>

      {/* ───────────── Pagination controls ───────────── */}
      <Pagination.Root
        count={total}
        pageSize={pageSize}
        page={pageIndex + 1}               /* Pagination is 1-based */
        onPageChange={(e) => goToPage(e.page - 1)}
        siblingCount={1}
      >
        <ButtonGroup
          variant="outline"
          size="sm"
          attached
          order={{ base: 1, md: 2 }}
        >
          {/* prev */}
          <Pagination.PrevTrigger asChild>
            <IconButton
              aria-label={t("previous")}
              disabled={pageIndex === 0}
            >
              <PrevIcon boxSize={4} />
            </IconButton>
          </Pagination.PrevTrigger>

          {/* numbered items / ellipsis */}
          <Pagination.Items
            render={(page) => (
              <IconButton
                key={`${page.type}-${page.value}`}
                variant={page.type === "page" ? "outline" : "solid"}
                type="button"
                {...(page.type === "page" ? { "aria-current": page.value === pageIndex + 1 ? "page" : undefined } : {})}
              >
                {page.type === "page" ? page.value : "…"}
              </IconButton>
            )}
          />

          {/* next */}
          <Pagination.NextTrigger asChild>
            <IconButton
              aria-label={t("next")}
              disabled={pageIndex + 1 >= pageCount}
            >
              <NextIcon boxSize={4} />
            </IconButton>
          </Pagination.NextTrigger>
        </ButtonGroup>
      </Pagination.Root>
    </HStack>
  );
};

export default PaginationWidget;
