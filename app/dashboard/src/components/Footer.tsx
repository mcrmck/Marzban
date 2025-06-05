import { HStack, Link, Text, StackProps } from "@chakra-ui/react";
import { ORGANIZATION_URL, REPO_URL } from "constants/Project";
import { useDashboard } from "../lib/stores/DashboardContext";
import { FC } from "react";

export const Footer: FC<StackProps> = (props) => {
  const { version } = useDashboard();
  return (
    <HStack w="full" py="0" position="relative" {...props}>
      <Text
        display="inline-block"
        flexGrow={1}
        textAlign="center"
        color="gray.500"
        fontSize="xs"
      >
        <Link color="jade.solid" href={REPO_URL}>
          Jade
        </Link>
        {version ? ` (v${version}), ` : ", "}
        Based on Marzban, Made with ❤️ in{" "}
        <Link color="jade.solid" href={ORGANIZATION_URL}>
          Gozargah
        </Link>
      </Text>
    </HStack>
  );
};
