import { NodeSelection } from './NodeSelection';

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
    <form onSubmit={form.handleSubmit((data) => mutate(data))}>
      <VStack spacing={4} align="stretch">
        // ... existing form fields ...

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