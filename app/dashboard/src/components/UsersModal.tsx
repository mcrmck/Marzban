import React, { FC } from 'react';
import { Box, Button, VStack } from '@chakra-ui/react';
import { NodeSelection } from './NodeSelection';
import { useTranslation } from 'react-i18next';
import { useDashboard } from '../contexts/DashboardContext';
// Assuming User type might be needed if editingUser was more deeply used here,
// but for now, it's correctly inferred from useDashboard.
// import { User } from "types/User";

type UserFormType = {
  form: {
    handleSubmit: (callback: (data: any) => void) => (e: React.FormEvent<HTMLFormElement>) => void;
  };
  mutate: (data: any) => void;
  isLoading: boolean;
  submitBtnText: React.ReactNode;
  btnProps?: React.ComponentProps<typeof Button>;
  btnLeftAdornment?: React.ReactNode;
};

const UserForm: FC<UserFormType> = ({
  form,
  mutate,
  isLoading,
  submitBtnText,
  btnProps,
  btnLeftAdornment,
}) => {
  const { t } = useTranslation();
  const { editingUser } = useDashboard(); // editingUser is of type User | null | undefined

  return (
    <form onSubmit={form.handleSubmit((data: any) => mutate(data))}>
      <VStack spacing={4} align="stretch">
        {/* ... existing form fields ... */}

        {editingUser && (
          <Box mt={4}>
            {/* Ensure NodeSelection component is updated to accept 'accountNumber'
              or a full 'user' object instead of 'username'.
            */}
            <NodeSelection accountNumber={editingUser.account_number} />
          </Box>
        )}

        <Button
          type="submit"
          colorScheme="blue" // Assuming blue, adjust if needed
          isLoading={isLoading}
          {...btnProps}
        >
          {btnLeftAdornment}
          {submitBtnText}
        </Button>
      </VStack>
    </form>
  );
};

export default UserForm;