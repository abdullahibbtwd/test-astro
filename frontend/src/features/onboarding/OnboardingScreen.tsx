import { space as dsSpace } from "../../design-system/theme/tokens";
import { ChartWheel } from "../../design-system/components/Ornament";
import { resolveRoute } from "../../lib/routes";
import { showSnackbar } from "../../design/components/Snackbar";
import { WheelPreview } from "../profiles/WheelPreview";
import { useState, useCallback } from "react";
import { Switch, View, Linking } from "react-native";
import { router, useLocalSearchParams, useFocusEffect } from "expo-router";
import * as Location from "expo-location";
import * as Notifications from "expo-notifications";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Field,
  Progress,
  Choices,
  Chip,
  ErrorNotice,
  Card,
} from "../../design/components";
import { PlaceSearch } from "../../design/components/PlaceSearch";
import { DateTimeField } from "../../design/components/DateTimeField";
import { useApp } from "../../lib/state";
import { useActions, useConfig } from "../../api/hooks";
import { validBirth, todayLocal } from "../../lib/dates";
import { JobProgress } from "../../design/components/JobProgress";
import { useGenerated } from "../../api/jobs";
import type { NatalReading } from "../../../contracts/spec-types";
import { mockToday } from "../../api/client";
import type { Place } from "../../../contracts/spec-types";
const steps = [
  "consent",
  "name",
  "birth-date",
  "birth-time",
  "birth-place",
  "current-place",
  "details",
  "notifications",
  "building",
];
export default function OnboardingScreen() {
  const { step = "consent" } = useLocalSearchParams<{ step: string }>(),
    app = useApp(),
    draft = app.draft,
    actions = useActions(),
    config = useConfig(),
    { t } = useTranslation();
  useFocusEffect(
    useCallback(() => {
      useApp.getState().editDraft({ step });
    }, [step]),
  );
  const [error, setError] = useState<unknown>(null);
  const go = (next: string) => {
    app.editDraft({ step: next });
    router.push(resolveRoute(`/(onboarding)/${next}`));
  };
  const run = async (task: () => Promise<void>) => {
    setError(null);
    try {
      await task();
    } catch (e) {
      setError(e);
    }
  };
  const current = async (place: Place) => {
    await actions.patchMe({ current_place_id: place.place_id });
    go("details");
  };
  const consent = async () => {
    await actions.patchMe({
      consents: {
        birth_data: {
          version: "DRAFT-preview-only",
          accepted_at: new Date().toISOString(),
        },
        marketing: draft.marketing,
      },
    });
    go("name");
  };
  const saveBirth = async (place: Place) => {
    app.editDraft({ place });
    const profile = await actions.saveProfile(
      {
        label: draft.name.trim(),
        relation: "self",
        birth_date: draft.date,
        birth_time: draft.time,
        birth_place_id: place.place_id,
      },
      draft.profileId,
    );
    app.editDraft({ profileId: profile.profile_id });
    app.update({
      activeProfileId: profile.profile_id,
      me: app.me ? { ...app.me, self_profile_id: profile.profile_id } : null,
    });
    go("current-place");
  };
  const allow = async (enabled: boolean) => {
    if (enabled) {
      const permission = await Notifications.requestPermissionsAsync();
      enabled = permission.granted;
    }
    if (app.me)
      await actions.patchMe({
        notification_prefs: { ...app.me.notification_prefs, enabled },
      });
    go("building");
  };
  return (
    <Screen headerless back>
      <Progress step={steps.indexOf(step) + 1} total={steps.length} />
      {["birth-date", "birth-time", "birth-place"].includes(step) && <View style={{ alignItems: "center" }}><ChartWheel width={180} /></View>}
      {step === "consent" ? (
        <>
          <Txt kind="display">{t("consentTitle")}</Txt>
          <Card>
            <View
              style={{ flexDirection: "row", gap: dsSpace[3], alignItems: "center" }}
            >
              <Switch
                accessibilityLabel={t("consent.birthData.placeholder")}
                value={draft.consent}
                onValueChange={(consent) => app.editDraft({ consent })}
              />
              <Txt style={{ flex: 1 }}>
                {t("consent.birthData.placeholder")}
              </Txt>
            </View>
          </Card>
          <View style={{ flexDirection: "row", gap: dsSpace[3], alignItems: "center" }}>
            <Switch
              accessibilityLabel={t("marketing")}
              value={draft.marketing}
              onValueChange={(marketing) => app.editDraft({ marketing })}
            />
            <Txt style={{ flex: 1 }}>{t("marketing")}</Txt>
          </View>
          <Choices>
            {(["privacy", "terms"] as const).map((kind) => (
              <Chip
                role="button"
                key={kind}
                label={t(kind)}
                selected={false}
                onPress={() => {
                  const url = config.data?.links[kind];
                  if (url) void Linking.openURL(url);
                  else showSnackbar(t("legalUnavailable"));
                }}
              />
            ))}
          </Choices>
          <Txt kind="caption" muted>
            {t("disclaimer")}
          </Txt>
          <Button
            label={t("continue")}
            disabled={!draft.consent}
            loading={actions.isPending}
            onPress={() => void run(consent)}
          />
        </>
      ) : null}
      {step === "name" ? (
        <>
          <Txt kind="display">{t("nameTitle")}</Txt>
          <Field
            label={t("name")}
            value={draft.name}
            maxLength={40}
            onChangeText={(name) => app.editDraft({ name })}
            autoComplete="name"
          />
          <Button
            label={t("continue")}
            disabled={!draft.name.trim()}
            loading={actions.isPending}
            onPress={() =>
              void run(async () => {
                const label = draft.name.trim();
                await actions.patchMe({ display_name: label });
                // Guest claim already saved birth — skip date/time/place.
                if (draft.profileId && app.me?.self_profile_id) {
                  await actions.saveProfile({ label }, draft.profileId);
                  go("current-place");
                } else go("birth-date");
              })
            }
          />
        </>
      ) : null}
      {step === "birth-date" ? (
        <>
          <Txt kind="display">{t("dateTitle")}</Txt>
          <DateTimeField
            mode="date"
            value={draft.date}
            onChange={(date) => app.editDraft({ date })}
          />
          <Button
            label={t("continue")}
            disabled={
              !validBirth(
                draft.date,
                "12:00",
                todayLocal(app.me?.current_place?.tz, mockToday),
              )
            }
            onPress={() => go("birth-time")}
          />
        </>
      ) : null}
      {step === "birth-time" ? (
        <>
          <Txt kind="display">{t("timeTitle")}</Txt>
          <DateTimeField
            mode="time"
            value={draft.time}
            onChange={(time) => app.editDraft({ time })}
          />
          <Txt muted>{t("timeHint")}</Txt>
          <Button
            label={t("continue")}
            disabled={
              !validBirth(
                draft.date,
                draft.time,
                todayLocal(app.me?.current_place?.tz, mockToday),
              )
            }
            onPress={() => go("birth-place")}
          />
        </>
      ) : null}
      {step === "birth-place" ? (
        <>
          <Txt kind="display">{t("placeTitle")}</Txt>
          <PlaceSearch
            onConfirm={(place) => void run(() => saveBirth(place))}
          />
        </>
      ) : null}
      {step === "current-place" ? (
        <>
          <Txt kind="display">{t("currentTitle")}</Txt>
          <Button
            secondary
            label={t("sameBirthplace")}
            onPress={() => {
              if (draft.place) void run(() => current(draft.place!));
            }}
          />
          <Button
            secondary
            label={t("useLocation")}
            onPress={() =>
              void run(async () => {
                const permission =
                  await Location.requestForegroundPermissionsAsync();
                if (!permission.granted) {
                  showSnackbar(t("locationHint"));
                  return;
                }
                const position = await Location.getCurrentPositionAsync({
                  accuracy: Location.Accuracy.Balanced,
                });
                const place = await actions.reverse(
                  position.coords.latitude,
                  position.coords.longitude,
                );
                if (place) await current(place);
                else showSnackbar(t("locationHint"));
              })
            }
          />
          <PlaceSearch onConfirm={(place) => void run(() => current(place))} />
        </>
      ) : null}
      {step === "details" ? (
        <>
          <Txt kind="display">{t("detailsTitle")}</Txt>
          <Txt muted>{t("optional")}</Txt>
          <Choices>
            {(["female", "male", "other", null] as const).map((gender) => (
              <Chip
                role="button"
                key={gender ?? "none"}
                label={t(gender ?? "preferNot")}
                selected={false}
                onPress={() =>
                  void run(async () => {
                    await actions.saveProfile({ gender }, draft.profileId);
                    go("notifications");
                  })
                }
              />
            ))}
          </Choices>
          <Button
            secondary
            label={t("skip")}
            onPress={() => go("notifications")}
          />
        </>
      ) : null}
      {step === "notifications" ? (
        <>
          <Txt kind="display">{t("notificationsTitle")}</Txt>
          <Txt muted>{t("notificationHint")}</Txt>
          <Button
            label={t("allow")}
            onPress={() => void run(() => allow(true))}
          />
          <Button
            secondary
            label={t("notNow")}
            onPress={() => void run(() => allow(false))}
          />
        </>
      ) : null}
      {step === "building" ? (
        <>
          <Txt kind="display">{t("buildingTitle")}</Txt>
          {draft.profileId && <WheelPreview id={draft.profileId} />}
          <Txt muted>{t("readingPending")}</Txt>
          {draft.profileId && <BuildingJob id={draft.profileId} />}
          <Card>
            <Txt>{draft.name}</Txt>
            <Txt muted>{draft.place?.name}</Txt>
            <Txt kind="caption">
              {draft.date} · {draft.time}
            </Txt>
          </Card>
          <Button
            label={t("continue")}
            onPress={() => {
              app.editDraft({ step: "complete" });
              router.replace("/(tabs)");
            }}
          />
        </>
      ) : null}
      <ErrorNotice error={error ?? actions.error} />
    </Screen>
  );
}

function BuildingJob({ id }: { id: string }) {
  const reading = useGenerated<NatalReading>(
    ["natal", id],
    `/profiles/${id}/natal-reading`,
    "NatalReading",
  );
  return reading.state === "ready" ? null : (
    <JobProgress
      job={reading.job}
      error={reading.error}
      slow={reading.slow}
      failed={reading.state === "failed"}
      retry={() => void reading.retry().catch(() => {})}
    />
  );
}
