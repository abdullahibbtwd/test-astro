import { ChartWheel } from "../../design-system/components/Ornament";
import { useState } from "react";
import { Alert, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { useProfiles, useActions } from "../../api/hooks";
import {
  Screen,
  Txt,
  Button,
  Field,
  Choices,
  Chip,
  Progress,
  Card,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { PlaceSearch } from "../../design/components/PlaceSearch";
import { DateTimeField } from "../../design/components/DateTimeField";
import { useApp } from "../../lib/state";
import { todayLocal, validBirth } from "../../lib/dates";
import { mockToday } from "../../api/client";
import type {
  Relation,
  Place,
  BirthProfile,
} from "../../../contracts/spec-types";
export default function ProfileEditor() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const profiles = useProfiles();
  const original = profiles.data?.find((p) => p.profile_id === id);
  if (id && !original)
    return (
      <Screen back>
        {profiles.isPending ? (
          <Skeleton />
        ) : (
          <ErrorNotice
            error={profiles.error ?? true}
            retry={() => void profiles.refetch()}
          />
        )}
      </Screen>
    );
  return <Editor key={id ?? "new"} original={original} id={id} />;
}
function Editor({ original, id }: { original?: BirthProfile; id?: string }) {
  const actions = useActions(),
    { t } = useTranslation(),
    me = useApp((s) => s.me),
    params = useLocalSearchParams<{ returnTo?: string; a?: string }>();
  const [step, setStep] = useState(0),
    [label, setLabel] = useState(original?.label ?? ""),
    [relation, setRelation] = useState<Relation>(
      original?.relation ?? "partner",
    ),
    [date, setDate] = useState(original?.birth.date ?? ""),
    [time, setTime] = useState(original?.birth.time ?? ""),
    [place, setPlace] = useState<Place | null>(original?.birth.place ?? null),
    [current, setCurrent] = useState<Place | null>(
      original?.current_place ?? null,
    );
  const changed =
    !!original &&
    (date !== original.birth.date ||
      time !== original.birth.time ||
      place?.place_id !== original.birth.place.place_id);
  const save = () => {
    const commit = () =>
      void actions
        .saveProfile(
          {
            label: label.trim(),
            relation,
            birth_date: date,
            birth_time: time,
            birth_place_id: place!.place_id,
            current_place_id: current?.place_id ?? null,
          },
          id,
        )
        .then((p) =>
          params.returnTo === "match"
            ? router.dismissTo(
                `/match/new?other=${p.profile_id}&a=${params.a ?? me?.self_profile_id ?? ""}`,
              )
            : router.replace(`/profile/charts/${p.profile_id}`),
        )
        .catch(() => {});
    if (changed)
      Alert.alert(t("edit"), t("recalculate"), [
        { text: t("cancel"), style: "cancel" },
        { text: t("continue"), onPress: commit },
      ]);
    else commit();
  };
  return (
    <Screen back title={t(id ? "edit" : "addPerson")}>
      <Progress step={step + 1} total={6} />
      {step >= 2 && step <= 4 && <View style={{ alignItems: "center" }}><ChartWheel width={180} /></View>}
      {step === 0 ? (
        <>
          <Txt kind="title">{t("relation")}</Txt>
          <Choices>
            {(original?.is_self
              ? ["self"]
              : [
                  "partner",
                  "child",
                  "parent",
                  "family",
                  "friend",
                  "colleague",
                  "business_partner",
                  "other",
                ]
            ).map((value) => (
              <Chip
                key={value}
                label={t(value)}
                selected={relation === value}
                onPress={() => setRelation(value as Relation)}
              />
            ))}
          </Choices>
        </>
      ) : null}
      {step === 1 ? (
        <Field
          label={t("personName")}
          value={label}
          maxLength={40}
          onChangeText={setLabel}
        />
      ) : null}
      {step === 2 ? (
        <DateTimeField mode="date" value={date} onChange={setDate} />
      ) : null}
      {step === 3 ? (
        <>
          <DateTimeField mode="time" value={time} onChange={setTime} />
          <Txt muted>{t("timeHint")}</Txt>
        </>
      ) : null}
      {step === 4 ? (
        <>
          <Txt kind="title">{t("birthPlace")}</Txt>
          {place ? (
            <Card>
              <Txt>
                {place.name} · {place.country_name}
              </Txt>
              <Button
                secondary
                label={t("change")}
                onPress={() => setPlace(null)}
              />
            </Card>
          ) : (
            <PlaceSearch onConfirm={setPlace} />
          )}
        </>
      ) : null}
      {step === 5 ? (
        <>
          <Txt kind="title">{t("currentTitle")}</Txt>
          <Txt muted>{t("optional")}</Txt>
          {current ? (
            <Card>
              <Txt>{current.name}</Txt>
              <Button
                secondary
                label={t("change")}
                onPress={() => setCurrent(null)}
              />
            </Card>
          ) : (
            <PlaceSearch onConfirm={setCurrent} />
          )}
        </>
      ) : null}
      {step > 0 && (
        <Button secondary label={t("back")} onPress={() => setStep(step - 1)} />
      )}
      <Button
        label={t(step === 5 ? "save" : "continue")}
        loading={actions.isPending}
        disabled={
          (step === 1 && !label.trim()) ||
          (step === 2 &&
            !validBirth(
              date,
              "12:00",
              todayLocal(me?.current_place?.tz, mockToday),
            )) ||
          (step === 3 &&
            !validBirth(
              date,
              time,
              todayLocal(me?.current_place?.tz, mockToday),
            )) ||
          (step === 4 && !place)
        }
        onPress={() => (step === 5 ? save() : setStep(step + 1))}
      />
      <ErrorNotice error={actions.error} />
    </Screen>
  );
}
