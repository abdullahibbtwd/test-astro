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
  onSelect: (date: string) => void;
}) {
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
              accessibilityLabel={`${date}${day ? `, ${day.label}${day.icons ? `, ${day.icons}` : ""}` : ""}`}
              accessibilityState={{ disabled: !day, selected: date === today }}
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
                    date === today
                      ? 3
                      : day &&
                          !["quiet", "neutral", "no_emphasis"].includes(
                            day.band,
                          )
                        ? 1.5
                        : 0,
                  borderColor:
                    date === today
                      ? c.accent
                      : bandColor(day?.band ?? "", c.bg === "#1A2030"),
                  backgroundColor: day?.tinted ? c.accentSoft : undefined,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Txt>{Number(date.slice(-2))}</Txt>
              </View>
              <Txt kind="caption" muted>
                {day?.icons ?? ""}
                {day?.band === "avoid" ? " /" : ""}
              </Txt>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
