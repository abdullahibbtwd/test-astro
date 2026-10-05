import CalendarScreen from "../calendar/CalendarScreen";
import { useEffect, useState } from "react";
import { Platform } from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { useApp } from "../../lib/state";
import { useProfiles, useCatalogue } from "../../api/hooks";
import { mockToday } from "../../api/client";
import { todayLocal, formatDate, formatMonth } from "../../lib/dates";
import { shiftDate, shiftMonth } from "../../lib/calendar";
import { privateStorage } from "../../lib/storage";
import { Screen, Button, ErrorNotice } from "../../design/components";
import { Segmented } from "../../design/components/Segmented";
import { DatePager } from "../../design/components/DatePager";
import { DayView, MonthView, YearView } from "./ForecastViews";
import type { Lens } from "../../../contracts/spec-types";
export default function AheadScreen() {
  const params = useLocalSearchParams<{
      view?: string;
      profile?: string;
      month?: string;
      date?: string;
      area?: string;
      lens?: string;
    }>(),
    { t } = useTranslation(),
    app = useApp(),
    profiles = useProfiles(),
    cat = useCatalogue();
  const profile = profiles.data?.find(
    (p) =>
      p.profile_id ===
      (app.activeProfileId ?? params.profile ?? app.me?.self_profile_id),
  );
  const update = app.update;
  useEffect(() => {
    if (params.profile) update({ activeProfileId: params.profile });
  }, [params.profile, update]);
  const today = todayLocal(
    profile?.is_self
      ? app.me?.current_place?.tz
      : (profile?.current_place?.tz ?? profile?.birth.tz),
    mockToday,
  );
  const view = params.view ?? (params.month ? "month" : "day");
  const [date, setDate] = useState(params.date ?? today),
    [month, setMonth] = useState(params.month ?? today.slice(0, 7)),
    [picker, setPicker] = useState(false);
  const [lenses, setLenses] = useState<Record<string, Lens>>(() => {
    try {
      return JSON.parse(privateStorage.getItem("forecast-lenses") ?? "{}");
    } catch {
      return {};
    }
  });
  useEffect(() => {
    if (params.date) setDate(params.date);
    if (params.month) setMonth(params.month);
  }, [params.date, params.month]);
  const lens: Lens = ["general", "personal", "professional"].includes(
    params.lens ?? "",
  )
    ? (params.lens as Lens)
    : (lenses[view] ?? "general");
  const monthLabel = (m: string) => formatMonth(m, app.language);
  const label =
    view === "day"
      ? formatDate(date, app.language)
      : view === "year"
        ? `${monthLabel(month)} – ${monthLabel(shiftMonth(month, 11))}`
        : monthLabel(month);
  const changeDate = (value: string) => {
    setDate(value);
    router.setParams({ date: value });
  };
  const changeMonth = (value: string) => {
    setMonth(value);
    router.setParams({ month: value, view });
  };
  const page = (n: number) => {
    if (view === "day") {
      const next = shiftDate(date, n);
      if (next >= shiftDate(today, -7) && next <= shiftDate(today, 365))
        changeDate(next);
    } else {
      const next = shiftMonth(month, n);
      if (
        next >= today.slice(0, 7) &&
        next <= shiftMonth(today.slice(0, 7), 11)
      )
        changeMonth(next);
    }
  };
  const pinned = (
    <>
      <Segmented
        value={view}
        onChange={(value) => {
          setPicker(false);
          router.setParams({ view: value, lens: undefined });
        }}
        items={["day", "month", "year", "calendar"].map((value) => ({
          value,
          label: t(value === "day" ? "today" : value),
        }))}
      />
      {view !== "calendar" && (
        <DatePager
          label={label}
          onPrevious={() => page(-1)}
          onNext={() => page(1)}
          onPick={() => setPicker(true)}
          onToday={
            (view === "day" ? date !== today : month !== today.slice(0, 7))
              ? () => {
                  if (view === "day") changeDate(today);
                  else changeMonth(today.slice(0, 7));
                }
              : undefined
          }
        />
      )}
      {view !== "calendar" && (
        <Segmented
          value={lens}
          items={(["general", "personal", "professional"] as const).map(
            (value) => ({
              value,
              label: t(
                value === "general"
                  ? "generalShort"
                  : value === "personal"
                    ? "loveShort"
                    : "workShort",
              ),
              accessibilityLabel: cat.data.lenses[value],
            }),
          )}
          onChange={(value) => {
            const next = { ...lenses, [view]: value };
            setLenses(next);
            router.setParams({ lens: value });
            privateStorage.setItem("forecast-lenses", JSON.stringify(next));
          }}
        />
      )}
      {picker && (
        <DateTimePicker
          value={new Date(`${view === "day" ? date : month + "-15"}T12:00:00`)}
          mode="date"
          minimumDate={
            new Date(
              `${view === "day" ? shiftDate(today, -7) : today}T00:00:00`,
            )
          }
          maximumDate={new Date(`${shiftDate(today, 365)}T23:59:59`)}
          onChange={(_, value) => {
            if (Platform.OS !== "ios") setPicker(false);
            if (value) {
              const day = `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
              if (view === "day") changeDate(day);
              else changeMonth(day.slice(0, 7));
            }
          }}
        />
      )}
      {picker && Platform.OS === "ios" && (
        <Button label={t("done")} onPress={() => setPicker(false)} />
      )}
    </>
  );
  return (
    <Screen embedded pinned={pinned}>
      {view === "calendar" ? (
        <CalendarScreen embedded />
      ) : (
        profile &&
        (view === "day" ? (
          <DayView
            profile={profile.profile_id}
            date={date}
            lens={lens}
            focusArea={params.area}
          />
        ) : view === "month" ? (
          <MonthView profile={profile.profile_id} month={month} lens={lens} />
        ) : (
          <YearView profile={profile.profile_id} month={month} lens={lens} />
        ))
      )}
      <ErrorNotice
        error={profiles.error}
        retry={() => void profiles.refetch()}
      />
    </Screen>
  );
}
