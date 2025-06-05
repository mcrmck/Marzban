import {
  Button,
  Menu,
  Portal,
} from "@chakra-ui/react";
import { LanguageIcon } from "@heroicons/react/24/outline";
import { FC, ReactNode } from "react";
import { useTranslation } from "react-i18next";

type HeaderProps = {
  actions?: ReactNode;
};

export const Language: FC<HeaderProps> = ({ actions }) => {
  const { i18n } = useTranslation();

  const changeLanguage = (lang: string) => {
    i18n.changeLanguage(lang);
  };

  return (
    <Menu.Root>
      <Menu.Trigger asChild>
        <Button
          size="sm"
          variant="outline"
          aria-label="Change language"
        >
          <LanguageIcon width={16} height={16} />
        </Button>
      </Menu.Trigger>
      <Portal>
        <Menu.Positioner>
          <Menu.Content minW="100px" zIndex={9999}>
            <Menu.Item value="en" onClick={() => changeLanguage("en")}>
              English
            </Menu.Item>
            <Menu.Item value="fa" onClick={() => changeLanguage("fa")}>
              فارسی
            </Menu.Item>
            <Menu.Item value="zh-cn" onClick={() => changeLanguage("zh-cn")}>
              简体中文
            </Menu.Item>
            <Menu.Item value="ru" onClick={() => changeLanguage("ru")}>
              Русский
            </Menu.Item>
          </Menu.Content>
        </Menu.Positioner>
      </Portal>
    </Menu.Root>
  );
};
