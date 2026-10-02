import CalendarScreen from "../calendar/CalendarScreen";
import { useEffect, useState } from "react";
import { ScrollView } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { useApp } from "../../lib/state";
import { useProfiles, useCatalogue } from "../../api/hooks";
import { mockToday } from "../../api/client";
import { todayLocal } from "../../lib/dates";
import { shiftDate, shiftMonth } from "../../lib/calendar";
import { privateStorage } from "../../lib/storage";
import { useTheme } from "../../design/theme";
import {
  Txt,
  Choices,
  Chip,
  Button,
  ErrorNotice,
} from "../../design/components";
import { DateTimeField } from "../../design/components/DateTimeField";
import { DayView, MonthView, YearView } from "./ForecastViews";
import type { Lens } from "../../../contracts/spec-types";
export default function AheadScreen() {
  const params = useLocalSearchParams<{
      view?: string;
      profile?: string;
      month?: string;
      date?: string;
      area?: string;
    }>(),
    { t } = useTranslation(),
    app = useApp(),
    profiles = useProfiles(),
    cat = useCatalogue(),
    c = useTheme();
  const profile = profiles.data?.find(
    (p) =>
      p.profile_id ===
      (params.profile ?? app.activeProfileId ?? app.me?.self_profile_id),
  );
  const today = todayLocal(
    profile?.is_self
      ? app.me?.current_place?.tz
      : (profile?.current_place?.tz ?? profile?.birth.tz),
    mockToday,
  );
  const view = params.view ?? (params.month ? "month" : "day");
  const [date, setDate] = useState(params.date ?? today),
    [month, setMonth] = useState(params.month ?? today.slice(0, 7));
  const [lenses, setLenses] = useState<Record<string, Lens>>(() =>
    JSON.parse(privateStorage.getItem("forecast-lenses") ?? "{}"),
  );
  useEffect(() => {
    if (params.date) setDate(params.date);
    if (params.month) setMonth(params.month);
  }, [params.date, params.month]);
  const lens = lenses[view] ?? "general";
  if (view === "calendar") return <CalendarScreen />;
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.bg }}
      contentContainerStyle={{ padding: 20, gap: 24 }}
    >
      <Choices>
        {profiles.data?.map((p) => (
          <Chip
            key={p.profile_id}
            label={p.label}
            selected={p.profile_id === profile?.profile_id}
            onPress={() => {
              app.update({ activeProfileId: p.profile_id });
              router.setParams({ profile: p.profile_id });
            }}
          />
        ))}
      </Choices>
      <Choices>
        {["day", "month", "year", "calendar"].map((value) => (
          <Chip
            key={value}
            label={t(value === "day" ? "today" : value)}
            selected={view === value}
            onPress={() => {
              if (value === "calendar")
                router.push(`/calendar?profile=${profile?.profile_id ?? ""}`);
              else router.setParams({ view: value });
            }}
          />
        ))}
      </Choices>
      <Choices>
        {(["general", "personal", "professional"] as const).map((value) => (
          <Chip
            key={value}
            label={cat.data.lenses[value]}
            selected={lens === value}
            onPress={() => {
              const next = { ...lenses, [view]: value };
              setLenses(next);
              privateStorage.setItem("forecast-lenses", JSON.stringify(next));
            }}
          />
        ))}
      </Choices>
      {view === "day" && (
        <>
          <Choices>
            <Button
              secondary
              label={t("previous")}
              disabled={date <= shiftDate(today, -7)}
              onPress={() => setDate(shiftDate(date, -1))}
            />
            <Button
              secondary
              label={t("today")}
              onPress={() => setDate(today)}
            />
            <Button
              secondary
              label={t("next")}
              disabled={date >= shiftDate(today, 365)}
              onPress={() => setDate(shiftDate(date, 1))}
            />
          </Choices>
          <DateTimeField
            mode="date"
            value={date}
            onChange={setDate}
            label={t("today")}
            minimumDate={new Date(`${shiftDate(today, -7)}T12:00:00`)}
            maximumDate={new Date(`${shiftDate(today, 365)}T12:00:00`)}
          />
        </>
      )}
      {view === "month" && (
        <>
          <Txt kind="title">
            {new Intl.DateTimeFormat(app.language, {
              month: "long",
              year: "numeric",
            }).format(new Date(`${month}-15T12:00:00`))}
          </Txt>
          <Choices>
            <Button
              secondary
              label={t("previous")}
              disabled={month <= today.slice(0, 7)}
              onPress={() => setMonth(shiftMonth(month, -1))}
            />
            <Button
              secondary
              label={t("next")}
              disabled={month >= shiftMonth(today.slice(0, 7), 11)}
              onPress={() => setMonth(shiftMonth(month, 1))}
            />
          </Choices>
        </>
      )}
      {profile &&
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
        ))}
      <ErrorNotice
        error={profiles.error}
        retry={() => {
          void profiles.refetch();
        }}
      />
    </ScrollView>
  );
}
