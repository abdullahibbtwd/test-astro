import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ICU from "i18next-icu";
import en from "./en.json";
import tr from "./tr.json";
void i18n
  .use(ICU)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, tr: { translation: tr } },
    lng: "tr",
    fallbackLng: "en",
    interpolation: { escapeValue: false },
  });
export default i18n;
