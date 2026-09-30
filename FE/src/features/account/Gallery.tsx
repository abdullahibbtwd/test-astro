import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Card,
  Chip,
  Choices,
  Field,
  Row,
  Skeleton,
  ErrorNotice,
  Progress,
} from "../../design/components";
import { useApp } from "../../lib/state";
export default function Gallery() {
  const { t } = useTranslation(),
    app = useApp(),
    [value, setValue] = useState("");
  if (!__DEV__) return null;
  return (
    <Screen back title={t("gallery")}>
      <Choices>
        {(["tr", "en"] as const).map((language) => (
          <Chip
            key={language}
            label={language}
            selected={app.language === language}
            onPress={() => app.update({ language })}
          />
        ))}
        {(["light", "dark"] as const).map((theme) => (
          <Chip
            key={theme}
            label={t(theme)}
            selected={app.theme === theme}
            onPress={() => app.update({ theme })}
          />
        ))}
      </Choices>
      <Txt kind="display">{t("welcome")}</Txt>
      <Txt kind="reading">{t("disclaimer")}</Txt>
      <Card>
        <Txt kind="title">{t("myCharts")}</Txt>
        <Row label={t("birthDate")} detail="30 Mart 1979" onPress={() => {}} />
      </Card>
      <Field label={t("name")} value={value} onChangeText={setValue} />
      <Button label={t("continue")} onPress={() => {}} />
      <Button secondary label={t("continue")} onPress={() => {}} />
      <Button disabled label={t("save")} onPress={() => {}} />
      <Button loading label={t("save")} onPress={() => {}} />
      <Button danger label={t("delete")} onPress={() => {}} />
      <Progress step={3} total={9} />
      <Skeleton />
      <ErrorNotice error={true} retry={() => {}} />
    </Screen>
  );
}
