import React, { FC } from 'react';
import { Box, Button, VStack } from '@chakra-ui/react';
import { NodeSelection } from './NodeSelection';
import { useTranslation } from 'react-i18next';
import { useDashboard } from '../contexts/DashboardContext';

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
  const { editingUser } = useDashboard();

  return (
    <form onSubmit={form.handleSubmit((data: any) => mutate(data))}>
      <VStack spacing={4} align="stretch">
        {/* ... existing form fields ... */}

        {editingUser && (
          <Box mt={4}>
            <NodeSelection username={editingUser.username} />
          </Box>
        )}

        <Button
          type="submit"
          colorScheme="blue"
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