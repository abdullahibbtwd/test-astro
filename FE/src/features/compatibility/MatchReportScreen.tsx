import { formatDate } from "../../lib/dates";
import Constants from "expo-constants";
import { exportPdf } from "../exports/native";
import { escapeHtml, paragraphs } from "../exports/document";
import { useState } from "react";
import { Share, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import * as Crypto from "expo-crypto";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Choices,
  Chip,
  Button,
  Card,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useApi } from "../../api/resource";
import { request } from "../../api/client";
import { useCatalogue } from "../../api/hooks";
import { useApp } from "../../lib/state";
import { useFlags } from "../../lib/flags";
import { Generated } from "../shared/Blocks";
import { ReadingSection } from "../profiles/ReadingScreen";
import type { Compatibility, CompatType } from "../../../contracts/spec-types";
export default function MatchReportScreen() {
  const { id } = useLocalSearchParams<{ id: string }>(),
    { t } = useTranslation(),
    cat = useCatalogue(),
    app = useApp(),
    flags = useFlags(),
    query = useApi<Compatibility>(`/compatibility/${id}`, "Compatibility"),
    data = query.data,
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const change = async (type: CompatType) => {
    if (!data || busy) return;
    setBusy(true);
    try {
      const result = await request<Compatibility>(
        "POST",
        "/compatibility",
        "Compatibility",
        {
          profile_a_id: data.people.a.profile_id,
          profile_b_id: data.people.b.profile_id,
          type,
          ...(type === "family"
            ? { family_relation: data.family_relation ?? "other" }
            : {}),
        },
        true,
        Crypto.randomUUID(),
      );
      router.replace(`/match/${result.compatibility_id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen
      back
      title={
        data
          ? `${data.people.a.label} & ${data.people.b.label}`
          : t("compatibility")
      }
    >
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Txt muted>
            {cat.data.compat_types[data.type]} ·{" "}
            {formatDate(data.created_at.slice(0, 10), app.language)}
          </Txt>
          <View style={{ gap: 12 }}>
            {[data.people.a, data.people.b].map((person) => (
              <Card key={person.profile_id}>
                <Txt kind="title">{person.label}</Txt>
                <Txt>
                  {cat.data.signs[person.big_three.sun]} ·{" "}
                  {cat.data.signs[person.big_three.moon]} ·{" "}
                  {cat.data.signs[person.big_three.ascendant]}
                </Txt>
                <Button
                  secondary
                  label={t("chart")}
                  onPress={() => {
                    app.update({ activeProfileId: person.profile_id });
                    router.push("/(tabs)/chart");
                  }}
                />
              </Card>
            ))}
          </View>
          <Choices>
            {(["love", "family", "work"] as const)
              .filter(
                (value) => value !== "family" || flags.familyCompatibility,
              )
              .map((value) => (
                <Chip
                  key={value}
                  label={cat.data.compat_types[value]}
                  selected={data.type === value}
                  onPress={() => {
                    void change(value);
                  }}
                />
              ))}
          </Choices>
          <Generated
            part={data.reading}
            retry={() => {
              void query.retry();
            }}
          >
            {(reading) => (
              <>
                {reading.sections.map((section, index) => (
                  <View key={section.key} style={{ gap: 16 }}>
                    <ReadingSection
                      section={section}
                      initialExpanded={index === 0}
                    />
                    {index === 0 && flags.compatibilityScore && data.score && (
                      <Txt>
                        {data.score.value} / 100 · {data.score.label}
                      </Txt>
                    )}
                  </View>
                ))}
                <Button
                  secondary
                  label={t("downloadPdf")}
                  disabled={busy}
                  onPress={() => {
                    setBusy(true);
                    void exportPdf(
                      reading.title,
                      `<h1>${escapeHtml(reading.title)}</h1><h2>${escapeHtml(data.people.a.label)} &amp; ${escapeHtml(data.people.b.label)}</h2>${reading.sections.map((s) => `<h2>${escapeHtml(s.title)}</h2>${paragraphs(s.text)}`).join("")}`,
                      t("disclaimer"),
                      Constants.expoConfig?.name ?? "Astrology",
                      `${data.people.a.label}-${data.people.b.label}`,
                    )
                      .catch(setError)
                      .finally(() => setBusy(false));
                  }}
                />
                <Button
                  secondary
                  label={t("share")}
                  onPress={() => {
                    void Share.share({
                      message: reading.sections
                        .map((s) => `${s.title}\n\n${s.text}`)
                        .join("\n\n"),
                    }).catch(setError);
                  }}
                />
              </>
            )}
          </Generated>
          {flags.askAstrology && (
            <Button
              secondary
              label={t("askRelationship")}
              onPress={() =>
                router.push(
                  `/ask?profile=${data.people.a.profile_id}&compatibility_id=${id}&other_profile_id=${data.people.b.profile_id}`,
                )
              }
            />
          )}
          <Txt kind="caption" muted>
            {t("disclaimer")}
          </Txt>
        </>
      )}
      <ErrorNotice
        error={error ?? query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    </Screen>
  );
}
