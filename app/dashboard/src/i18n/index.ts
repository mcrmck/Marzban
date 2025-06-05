import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import language files from src/statics/locales
import enTranslation from '../statics/locales/en.json';
import zhTranslation from '../statics/locales/zh.json';
import ruTranslation from '../statics/locales/ru.json';
import faTranslation from '../statics/locales/fa.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        translation: enTranslation
      },
      zh: {
        translation: zhTranslation
      },
      ru: {
        translation: ruTranslation
      },
      fa: {
        translation: faTranslation
      }
    },
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;