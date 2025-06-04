import {
  chakra,
  Field,
  InputGroup,
  InputAddon,
  InputElement,
  Textarea as ChakraTextarea,
  TextareaProps as ChakraTextareaProps,
  Box,
} from "@chakra-ui/react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import classNames from "classnames";
import React, { PropsWithChildren, ReactNode } from "react";

const ClearIcon = chakra(XMarkIcon);

export type TextareaProps = PropsWithChildren<
  {
    value?: string;
    className?: string;
    endAdornment?: ReactNode;
    startAdornment?: ReactNode;
    type?: string;
    placeholder?: string;
    onChange?: (e: any) => void;
    onBlur?: (e: any) => void;
    onClick?: (e: any) => void;
    name?: string;
    error?: string;
    disabled?: boolean;
    label?: string;
    clearable?: boolean;
  } & ChakraTextareaProps
>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      disabled,
      label,
      className,
      startAdornment,
      endAdornment,
      placeholder,
      onChange,
      onBlur,
      name,
      value,
      onClick,
      error,
      clearable = false,
      ...props
    },
    ref
  ) => {
    const clear = () => {
      if (onChange)
        onChange({
          target: {
            value: "",
            name,
          },
        });
    };
    const { size = "md" } = props;

    return (
      <Field.Root invalid={!!error}>
        {label && <Field.Label>{label}</Field.Label>}
        <InputGroup
          w="full"
          rounded="md"
          _focusWithin={{
            outline: "2px solid",
            outlineColor: "primary.200",
          }}
          bg={disabled ? "gray.100" : "transparent"}
          _dark={{ bg: disabled ? "gray.600" : "transparent" }}
        >
          <>
            {startAdornment && <InputAddon>{startAdornment}</InputAddon>}
            <Box position="relative" flex={1}>
              <ChakraTextarea
                name={name}
                ref={ref}
                className={classNames(className)}
                placeholder={placeholder}
                onChange={onChange}
                onBlur={onBlur}
                value={value}
                onClick={onClick}
                disabled={disabled}
                flexGrow={1}
                size={size}
                _focusVisible={{
                  outline: "none",
                  borderTopColor: "transparent",
                  borderRightColor: "transparent",
                  borderBottomColor: "transparent",
                }}
                _disabled={{
                  cursor: "not-allowed",
                }}
                {...props}
                roundedLeft={startAdornment ? "0" : "md"}
                roundedRight={endAdornment ? "0" : "md"}
                paddingRight={clearable && value ? "2.5rem" : undefined}
              />
              {clearable && value && value.length && (
                <Box
                  position="absolute"
                  right="0.75rem"
                  top="50%"
                  transform="translateY(-50%)"
                  display="flex"
                  alignItems="center"
                >
                  <ClearIcon
                    w={4}
                    h={4}
                    onClick={clear}
                    cursor="pointer"
                  />
                </Box>
              )}
            </Box>
            {endAdornment && (
              <InputAddon
                borderLeftRadius={0}
                borderRightRadius="6px"
                bg="transparent"
              >
                {endAdornment}
              </InputAddon>
            )}
          </>
        </InputGroup>
        {!!error && <Field.ErrorText>{error}</Field.ErrorText>}
      </Field.Root>
    );
  }
);
