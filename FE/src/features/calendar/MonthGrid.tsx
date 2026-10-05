import { useTranslation } from "react-i18next";
import { formatDay } from "../../lib/dates";
import { Pressable, View } from "react-native";
import { useApp } from "../../lib/state";
import { useTheme } from "../../design/theme";
import { Txt } from "../../design/components";
import { bandColor } from "../../design/bands";
import { monthDays } from "../../lib/calendar";
export function MonthGrid({
  month,
  days,
  today,
  selected,
  bestDays = false,
  onSelect,
}: {
  month: string;
  days: {
    date: string;
    band: string;
    label: string;
    icons?: string;
    tinted?: boolean;
  }[];
  today?: string;
  selected?: string;
  bestDays?: boolean;
  onSelect: (date: string) => void;
}) {
  const { t } = useTranslation();
  const iconNames = (icons = "") =>
    icons
      .split(" ")
      .map(
        (icon) =>
          ({
            "○": t("newMoon"),
            "●": t("fullMoon"),
            "◐": t("eclipse"),
            "↺": t("station"),
          })[icon],
      )
      .filter(Boolean)
      .join(", ");
  const lang = useApp((s) => s.language),
    c = useTheme(),
    grid = monthDays(month),
    byDate = new Map(days.map((d) => [d.date, d]));
  return (
    <View style={{ gap: 6 }}>
      <View style={{ flexDirection: "row" }}>
        {Array.from({ length: 7 }, (_, i) => (
          <View key={i} style={{ width: "14.2857%", alignItems: "center" }}>
            <Txt kind="caption">
              {new Intl.DateTimeFormat(lang, {
                weekday: "short",
                timeZone: "UTC",
              }).format(new Date(Date.UTC(2026, 8, 28 + i)))}
            </Txt>
          </View>
        ))}
      </View>
      <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
        {Array.from({ length: grid.offset }, (_, i) => (
          <View key={`blank${i}`} style={{ width: "14.2857%" }} />
        ))}
        {grid.dates.map((date) => {
          const day = byDate.get(date);
          return (
            <Pressable
              key={date}
              accessibilityRole="button"
              accessibilityLabel={`${formatDay(date, lang)}${day ? `, ${day.label}${day.icons ? `, ${iconNames(day.icons)}` : ""}` : ""}`}
              accessibilityState={{
                disabled: !day,
                selected: date === selected,
              }}
              disabled={!day}
              onPress={() => onSelect(date)}
              style={{
                width: "14.2857%",
                minHeight: 64,
                padding: 3,
                alignItems: "center",
                justifyContent: "center",
                opacity: day ? 1 : 0.3,
              }}
            >
              <View
                style={{
                  minWidth: 40,
                  minHeight: 40,
                  padding: 4,
                  borderRadius: 20,
                  borderWidth:
                    day &&
                    [
                      "plus",
                      "minus",
                      "favorable",
                      "supportive",
                      "strongly_supportive",
                      "challenging",
                      "excellent",
                      "good",
                      "avoid",
                    ].includes(day.band)
                      ? 1.5
                      : 0,
                  borderStyle: day?.band === "avoid" ? "dashed" : "solid",
                  borderColor: bandColor(day?.band ?? "", c.bg === "#1A2030"),
                  backgroundColor: date === selected ? c.accentSoft : undefined,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Txt
                  style={
                    date === today
                      ? { fontFamily: "Inter-SemiBold" }
                      : undefined
                  }
                >
                  {Number(date.slice(-2))}
                </Txt>
                {date === today && (
                  <View
                    style={{
                      width: 4,
                      height: 4,
                      borderRadius: 2,
                      backgroundColor: c.accent,
                    }}
                  />
                )}
              </View>
              <Txt kind="caption" muted>
                {day?.icons ?? ""}
                {day?.band === "avoid" ? " /" : ""}
              </Txt>
            </Pressable>
          );
        })}
      </View>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {(bestDays
          ? ["excellent", "good", "avoid"]
          : ["favorable", "challenging"]
        ).map((band) => (
          <View key={band} accessible accessibilityLabel={t(band)} style={{flexDirection:"row",alignItems:"center",gap:6}}><View style={{width:20,height:20,borderRadius:10,borderWidth:1.5,borderStyle:band === "avoid" ? "dashed" : "solid",borderColor:bandColor(band,c.bg === "#1A2030")}}/><Txt kind="caption">{t(band)}</Txt></View>
        ))}
        {[...new Set(days.flatMap((d) => (d.icons ?? "").split(" ")))]
          .filter((icon) => iconNames(icon))
          .map((icon) => (
            <Txt key={icon} kind="caption">
              {icon} {iconNames(icon)}
            </Txt>
          ))}
      </View>
    </View>
  );
}
