import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { useProfiles } from "../../api/hooks";
import {
  Screen,
  Txt,
  Card,
  Button,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useApp } from "../../lib/state";
export default function LocalHomeScreen() {
  const { t } = useTranslation(),
    profiles = useProfiles(),
    app = useApp();
  return (
    <Screen title={t("realChartPreview")}>
      <Card>
        <Txt>{t("realChartDescription")}</Txt>
        <Txt muted>{t("localServicesPending")}</Txt>
      </Card>
      {profiles.isPending && <Skeleton />}
      <ErrorNotice
        error={profiles.error}
        retry={() => void profiles.refetch()}
      />
      {profiles.data?.map((profile) => (
        <Card key={profile.profile_id}>
          <Txt kind="title">{profile.label}</Txt>
          <Txt muted>
            {profile.birth.date} · {profile.birth.time} ·{" "}
            {profile.birth.place.name}
          </Txt>
          <Button
            label={t("chart")}
            onPress={() => {
              app.update({ activeProfileId: profile.profile_id });
              router.push("/(tabs)/chart");
            }}
          />
          <Button
            secondary
            label={t("reading")}
            onPress={() =>
              router.push(`/chart/reading?profile=${profile.profile_id}`)
            }
          />
          <Button
            secondary
            label={t("ahead")}
            onPress={() =>
              router.push(`/(tabs)/ahead?profile=${profile.profile_id}`)
            }
          />
        </Card>
      ))}
      <Button
        secondary
        label={t("addPerson")}
        onPress={() => router.push("/profile/charts/new")}
      />
      <Button
        secondary
        label={t("calendar")}
        onPress={() => router.push("/calendar")}
      />
      <Button
        secondary
        label={t("bestDays")}
        onPress={() => router.push("/best-days")}
      />
    </Screen>
  );
}
