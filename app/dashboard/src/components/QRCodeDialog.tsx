/* ----------------------------------------------------------------------
 * QRCodeDialog.tsx – Chakra UI v3 compatible
 * ------------------------------------------------------------------- */

import {
  Box,
  Dialog,
  HStack,
  Icon,
  VStack,
  IconButton,
  Text,
} from "@chakra-ui/react";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  QrCodeIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { QRCodeCanvas } from "qrcode.react";
import { FC, useState } from "react";
import { useTranslation } from "react-i18next";
import Slider from "react-slick";
import "slick-carousel/slick/slick.css";
import "slick-carousel/slick/slick-theme.css";

import { useDashboard } from "../lib/stores/DashboardContext";

export const QRCodeDialog: FC = () => {
  const { QRcodeLinks, setQRCode, setSubLink, subscribeUrl } = useDashboard();
  const { t } = useTranslation();

  const [index, setIndex] = useState(0);
  const isOpen = QRcodeLinks !== null;

  /* close handler ------------------------------------------------------ */
  const onClose = () => {
    setQRCode(null);
    setSubLink(null);
  };

  /* make subscription link absolute if needed -------------------------- */
  const subscribeQrLink = String(subscribeUrl).startsWith("/")
    ? window.location.origin + subscribeUrl
    : String(subscribeUrl);

  /* ------------------------------------------------------------------- */
  /* Slider arrow factories (react-slick expects plain elements)         */
  /* ------------------------------------------------------------------- */
  const NextArrow: FC<any> = (props) => (
    <IconButton
      {...props}
      aria-label="next"
      size="sm"
      pos="absolute"
      right="-4"
      top="50%"
      transform="translateY(-50%)"
    >
      <ChevronRightIcon className="h-6 w-6 text-gray-600 dark:text-white" />
    </IconButton>
  );

  const PrevArrow: FC<any> = (props) => (
    <IconButton
      {...props}
      aria-label="previous"
      size="sm"
      pos="absolute"
      left="-4"
      top="50%"
      transform="translateY(-50%)"
    >
      <ChevronLeftIcon className="h-6 w-6 text-gray-600 dark:text-white" />
    </IconButton>
  );

  /* ------------------------------------------------------------------- */
  /* JSX                                                                 */
  /* ------------------------------------------------------------------- */
  return (
    <Dialog.Root open={isOpen} onOpenChange={(d) => !d.open && onClose()}>
      <Dialog.Backdrop bg="blackAlpha.300" backdropFilter="blur(10px)" />

      <Dialog.Positioner>
        <Dialog.Content mx="3" w="fit-content" maxW="3xl">
          {/* ── Header ─────────────────────────────────────────────── */}
          <HStack pt={6} px={6} gap={3}>
            <Icon color="primary">
              <QrCodeIcon className="h-5 w-5 text-white" />
            </Icon>
            <Box flex="1" />
            <Dialog.CloseTrigger asChild>
              <IconButton aria-label={t("close")} size="sm" variant="ghost">
                <XMarkIcon className="h-4 w-4" />
              </IconButton>
            </Dialog.CloseTrigger>
          </HStack>

          {/* ── Body ───────────────────────────────────────────────── */}
          {QRcodeLinks && (
            <Box
              display="flex"
              flexDir={{ base: "column", lg: "row" }}
              justifyContent="center"
              gap={{ base: 8, lg: 16 }}
              px={{ base: 12, lg: 0 }}
              py={8}
            >
              {/* Subscription link (left) */}
              {subscribeUrl && (
                <VStack>
                  <QRCodeCanvas
                    value={subscribeQrLink}
                    size={300}
                    includeMargin={false}
                    level="L"
                    style={{ background: "white", padding: "8px" }}
                  />
                  <Text textAlign="center" pt={1}>
                    {t("qrcodeDialog.sublink")}
                  </Text>
                </VStack>
              )}

              {/* Per-node QR codes (right) */}
              <Box w="300px" pos="relative">
                <Slider
                  arrows
                  dots={false}
                  infinite
                  slidesToShow={1}
                  slidesToScroll={1}
                  afterChange={setIndex}
                  nextArrow={<NextArrow />}
                  prevArrow={<PrevArrow />}
                >
                  {QRcodeLinks.map((link, i) => (
                    <HStack key={i} justify="center">
                      <QRCodeCanvas
                        value={link}
                        size={300}
                        includeMargin={false}
                        level="L"
                        style={{ background: "white", padding: "8px" }}
                      />
                    </HStack>
                  ))}
                </Slider>

                <Text textAlign="center" pt={3}>
                  {index + 1} / {QRcodeLinks.length}
                </Text>
              </Box>
            </Box>
          )}
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
};
