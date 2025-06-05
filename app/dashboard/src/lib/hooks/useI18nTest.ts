/**
 * Test hook to verify i18n is working properly with React 19
 */
import { useTranslation } from 'react-i18next';
import { useEffect } from 'react';

export const useI18nTest = () => {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    // Test that i18n is initialized
    console.log('i18n initialized:', i18n.isInitialized);
    console.log('Current language:', i18n.language);
    console.log('Available languages:', i18n.languages);
    
    // Test a translation
    const testTranslation = t('app.name');
    console.log('Test translation (app.name):', testTranslation);
    
    if (testTranslation === 'app.name') {
      console.warn('Translation not working - key returned as-is');
    } else {
      console.log('✅ Translation working correctly');
    }
  }, [t, i18n]);

  return { t, i18n };
};