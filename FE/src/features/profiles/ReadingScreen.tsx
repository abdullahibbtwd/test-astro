import { resolveRoute } from "../../lib/routes";
import { useFlags } from "../../lib/flags";
import {
  BottomSheetModal,
  BottomSheetScrollView,
  BottomSheetBackdrop,
} from "@gorhom/bottom-sheet";
import { useTheme } from "../../design/theme";
import { useRef, useState } from "react";
import { Pressable, Share, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Choices,
  Row,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { JobProgress } from "../../design/components/JobProgress";
import { useProfiles } from "../../api/hooks";
import { useGenerated } from "../../api/jobs";
import { useApp } from "../../lib/state";
import type {
  BirthProfile,
  NatalReading,
  NatalSection,
} from "../../../contracts/spec-types";
export default function ReadingScreen() {
  const params = useLocalSearchParams<{ profile?: string; key?: string }>();
  const profiles = useProfiles(),
    app = useApp(),
    { t } = useTranslation();
  const id = params.profile ?? app.activeProfileId ?? app.me?.self_profile_id;
  const profile = profiles.data?.find((p) => p.profile_id === id);
  if (!profile)
    return (
      <Screen back title={t("reading")}>
        {profiles.isPending ? (
          <Skeleton />
        ) : (
          !profiles.error && <Txt>{t("missingProfile")}</Txt>
        )}
        <ErrorNotice
          error={profiles.error}
          retry={() => {
            void profiles.refetch();
          }}
        />
      </Screen>
    );
  return (
    <ReadingContent
      key={`${profile.profile_id}:${profile.chart_key}:${app.language}`}
      profile={profile}
      sectionKey={params.key}
    />
  );
}
function ReadingContent({
  profile,
  sectionKey,
}: {
  profile: BirthProfile;
  sectionKey?: string;
}) {
  const { t } = useTranslation();
  const reading = useGenerated<NatalReading>(
    ["natal", profile.profile_id, profile.chart_key],
    `/profiles/${profile.profile_id}/natal-reading`,
    "NatalReading",
  );
  const [all, setAll] = useState<boolean | null>(null);
  const contents = useRef<BottomSheetModal>(null),
    c = useTheme();
  const sections = sectionKey
    ? reading.data?.sections.filter((section) => section.key === sectionKey)
    : reading.data?.sections;
  return (
    <Screen back title={profile.label}>
      {!reading.data ? (
        reading.state === "loading" ? (
          <Skeleton />
        ) : (
          <JobProgress
            error={reading.error}
            job={reading.job}
            slow={reading.slow}
            failed={reading.state === "failed"}
            retry={() => {
              void reading.retry();
            }}
          />
        )
      ) : (
        <>
          <Txt kind="caption" muted>
            {reading.data.title}
          </Txt>
          <Txt muted>{t("readingIntro")}</Txt>
          {sectionKey ? (
            <Button
              secondary
              label={t("backToReading")}
              onPress={() =>
                router.replace(`/chart/reading?profile=${profile.profile_id}`)
              }
            />
          ) : (
            <>
              <Choices>
                <Button
                  secondary
                  label={t(all ? "collapseAll" : "expandAll")}
                  onPress={() => setAll(!all)}
                />
                <Button
                  secondary
                  label={t("contents")}
                  onPress={() => contents.current?.present()}
                />
              </Choices>
              <BottomSheetModal
                ref={contents}
                snapPoints={["60%", "90%"]}
                enableDynamicSizing={false}
                backgroundStyle={{ backgroundColor: c.surface }}
                handleIndicatorStyle={{ backgroundColor: c.ink2 }}
                backdropComponent={(props) => (
                  <BottomSheetBackdrop
                    {...props}
                    appearsOnIndex={0}
                    disappearsOnIndex={-1}
                  />
                )}
              >
                <BottomSheetScrollView
                  contentContainerStyle={{
                    padding: 24,
                    paddingBottom: 48,
                    gap: 12,
                  }}
                >
                  <Txt kind="title">{t("contents")}</Txt>
                  <Button
                    secondary
                    label={t("close")}
                    onPress={() => contents.current?.dismiss()}
                  />
                  {reading.data.sections.map((section) => (
                    <Row
                      key={section.key}
                      label={section.title}
                      onPress={() => {
                        contents.current?.dismiss();
                        router.push(
                          `/chart/section/${section.key}?profile=${profile.profile_id}`,
                        );
                      }}
                    />
                  ))}
                </BottomSheetScrollView>
              </BottomSheetModal>
            </>
          )}
          {!sections?.length && <Txt>{t("missingSection")}</Txt>}
          {reading.data.parts.map((part) => (
            <View key={part.movement} style={{ gap: 24 }}>
              {sections?.some(
                (section) => section.movement === part.movement,
              ) && <Txt kind="title">{part.title}</Txt>}
              {sections
                ?.filter((section) => section.movement === part.movement)
                .map((section) => (
                  <ReadingSection
                    key={`${section.key}:${all}`}
                    section={section}
                    askRoute={`/ask?profile=${profile.profile_id}&section_key=${section.key}`}
                    initialExpanded={
                      !!sectionKey ||
                      all ||
                      section === reading.data?.sections[0]
                    }
                  />
                ))}
            </View>
          ))}
        </>
      )}
    </Screen>
  );
}
export function ReadingSection({
  section,
  initialExpanded,
  askRoute,
}: {
  section: Pick<NatalSection, "title" | "text">;
  initialExpanded: boolean;
  askRoute?: string;
}) {
  const { t } = useTranslation(),
    flags = useFlags();
  const [expanded, setExpanded] = useState(initialExpanded),
    [copied, setCopied] = useState(false),
    [error, setError] = useState<unknown>();
  const text = `${section.title}\n\n${section.text}`;
  const perform = async (task: () => Promise<unknown>) => {
    setError(undefined);
    try {
      await task();
    } catch (e) {
      setError(e);
    }
  };
  return (
    <View style={{ gap: 16 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={section.title}
        accessibilityState={{ expanded }}
        onPress={() => setExpanded(!expanded)}
        style={{ minHeight: 48, justifyContent: "center" }}
      >
        <Txt kind="title">{section.title}</Txt>
      </Pressable>
      <Txt kind="reading" numberOfLines={expanded ? undefined : 2}>
        {section.text}
      </Txt>
      {expanded && (
        <Choices>
          {askRoute && flags.askAstrology && (
            <Button
              secondary
              label={t("ask")}
              onPress={() => router.push(resolveRoute(askRoute))}
            />
          )}
          <Button
            secondary
            label={t(copied ? "copied" : "copy")}
            onPress={() => {
              void perform(async () => {
                await Clipboard.setStringAsync(text);
                setCopied(true);
              });
            }}
          />
          <Button
            secondary
            label={t("share")}
            onPress={() => {
              void perform(() =>
                Share.share({ title: section.title, message: text }),
              );
            }}
          />
        </Choices>
      )}
      <ErrorNotice error={error} />
    </View>
  );
}
