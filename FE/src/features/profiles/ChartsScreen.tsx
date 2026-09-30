import { Glyph } from "../../design/components/Glyph";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { useProfiles, useCatalogue } from "../../api/hooks";
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
    catalogue = useCatalogue(),
    lang = useApp((s) => s.language);
  return (
    <Screen back title={t("myCharts")}>
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
        error={profiles.error}
        retry={() => void profiles.refetch()}
      />
    </Screen>
  );
}
