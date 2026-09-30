import { useState } from "react";
import { router } from "expo-router";
import { getCalendars } from "expo-localization";
import { useTranslation } from "react-i18next";
import { useApp } from "../../lib/state";
import { Card, Txt, Button, Choices } from "../../design/components";
export function TimezoneNotice() {
  const app = useApp(),
    { t } = useTranslation(),
    [dismissed, setDismissed] = useState(""),
    device = getCalendars()[0]?.timeZone,
    stored = app.me?.current_place?.tz,
    key = `${device}:${stored}`;
  if (!device || !stored || device === stored || dismissed === key) return null;
  return (
    <Card>
      <Txt>{t("timezoneChanged", { zone: device })}</Txt>
      <Choices>
        <Button
          secondary
          label={t("updateLocation")}
          onPress={() => router.push("/profile/location")}
        />
        <Button
          secondary
          label={t("close")}
          onPress={() => setDismissed(key)}
        />
      </Choices>
    </Card>
  );
}
