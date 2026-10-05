import { Alert } from "react-native";
import { Glyph } from "../../design/components/Glyph";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { useProfiles, useCatalogue, useActions } from "../../api/hooks";
import {
  Screen,
  Txt,
  Button,
  Row,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useApp } from "../../lib/state";
import { formatDate } from "../../lib/dates";
export default function ChartsScreen() {
  const { t } = useTranslation(),
    profiles = useProfiles(),
    actions = useActions(),
    catalogue = useCatalogue(),
    lang = useApp((s) => s.language);
  return (
    <Screen list largeTitle back title={t("myCharts")}>
      <Txt muted>{t("homeBody")}</Txt>
      {profiles.isPending ? (
        <Skeleton />
      ) : (
        <>
          {[...(profiles.data ?? [])]
            .sort(
              (a, b) =>
                Number(b.is_self) - Number(a.is_self) ||
                a.created_at.localeCompare(b.created_at),
            )
            .map((p) => (
              <Row
                key={p.profile_id}
                leading={<Glyph name={p.big_three.sun} />}
                label={`${p.label}${p.is_self ? ` · ${t("you")}` : ""}`}
                detail={`${catalogue.data?.relations[p.relation] ?? t(p.relation)} · ${formatDate(p.birth.date, lang)}`}
                onPress={() => router.push(`/profile/charts/${p.profile_id}`)}
                onLongPress={
                  p.is_self
                    ? undefined
                    : () =>
                        Alert.alert(
                          t("deletePerson", { name: p.label }),
                          t("deletePersonBody"),
                          [
                            { text: t("cancel"), style: "cancel" },
                            {
                              text: t("delete"),
                              style: "destructive",
                              onPress: () => {
                                void actions
                                  .removeProfile(p.profile_id)
                                  .then(() => {
                                    if (
                                      useApp.getState().activeProfileId ===
                                      p.profile_id
                                    )
                                      useApp.getState().update({
                                        activeProfileId:
                                          useApp.getState().me?.self_profile_id,
                                      });
                                  })
                                  .catch(() => {});
                              },
                            },
                          ],
                        )
                }
              />
            ))}
          <Button
            label={t("addPerson")}
            disabled={(profiles.data?.length ?? 0) >= 50}
            onPress={() => router.push("/profile/charts/new")}
          />
        </>
      )}
      <ErrorNotice
        error={profiles.error ?? actions.error}
        retry={() => void profiles.refetch()}
      />
    </Screen>
  );
}
