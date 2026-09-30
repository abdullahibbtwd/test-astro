import { Alert } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { useProfiles, useCatalogue, useActions } from "../../api/hooks";
import {
  Screen,
  Txt,
  Card,
  Button,
  Row,
  Choices,
  Chip,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useApp } from "../../lib/state";
import { formatDate } from "../../lib/dates";
export default function ProfileDetail() {
  const { id } = useLocalSearchParams<{ id: string }>(),
    { t } = useTranslation(),
    profiles = useProfiles(),
    catalogue = useCatalogue(),
    actions = useActions(),
    app = useApp();
  const profile = profiles.data?.find((p) => p.profile_id === id);
  if (!profile)
    return (
      <Screen back>
        <Skeleton />
        <ErrorNotice
          error={profiles.error}
          retry={() => void profiles.refetch()}
        />
      </Screen>
    );
  const remove = () =>
    Alert.alert(
      t("deletePerson", { name: profile.label }),
      t("deletePersonBody"),
      [
        { text: t("cancel"), style: "cancel" },
        {
          text: t("delete"),
          style: "destructive",
          onPress: () =>
            void actions
              .removeProfile(id)
              .then(() => {
                if (app.activeProfileId === id)
                  app.update({ activeProfileId: app.me?.self_profile_id });
                router.dismissTo("/profile/charts");
              })
              .catch(() => {}),
        },
      ],
    );
  return (
    <Screen back>
      <Txt kind="display">{profile.label}</Txt>
      <Txt muted>
        {catalogue.data?.relations[profile.relation] ?? t(profile.relation)}
      </Txt>
      <Card>
        {(["sun", "moon", "ascendant"] as const).map((key) => (
          <Row
            key={key}
            label={t(key === "ascendant" ? "rising" : key)}
            detail={catalogue.data?.signs[profile.big_three[key]]}
          />
        ))}
      </Card>
      <Row
        label={t("birthDate")}
        detail={formatDate(profile.birth.date, app.language)}
      />
      <Row label={t("birthTime")} detail={profile.birth.time} />
      <Row
        label={t("birthPlace")}
        detail={`${profile.birth.place.name} · ${profile.birth.place.country_name}`}
      />
      <Row label={t("timeZone")} detail={profile.birth.tz} />
      <Choices>
        {(["chart", "ahead", "map"] as const).map((tab) => (
          <Chip
            key={tab}
            label={t(tab)}
            selected={false}
            onPress={() => {
              app.update({ activeProfileId: id });
              router.push(`/(tabs)/${tab}`);
            }}
          />
        ))}
      </Choices>
      {!profile.is_self && (
        <Button
          secondary
          label={t("compare")}
          onPress={() => router.push(`/(tabs)/match?other=${id}`)}
        />
      )}
      <Button
        label={t("edit")}
        onPress={() => router.push(`/profile/charts/new?id=${id}`)}
      />
      {!profile.is_self && (
        <Button secondary danger label={t("delete")} onPress={remove} />
      )}
      <ErrorNotice error={actions.error} />
    </Screen>
  );
}
