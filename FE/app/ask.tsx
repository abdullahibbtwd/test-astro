import { Screen, Txt } from "../src/design/components";
import { useTranslation } from "react-i18next";
export default function Ask() {
  const { t } = useTranslation();
  return (
    <Screen back title={t("ask")}>
      <Txt muted>{t("phaseMessage")}</Txt>
    </Screen>
  );
}
