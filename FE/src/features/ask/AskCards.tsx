import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Card, Txt, Button } from "../../design/components";
import { useCatalogue } from "../../api/hooks";
import { useApp } from "../../lib/state";
import { degrees } from "../chart/facts";
import type { AskCard } from "../../../contracts/spec-types";
export function AskCardView({
  card,
  profile,
}: {
  card: AskCard;
  profile: string;
}) {
  const c = useCatalogue().data,
    { t } = useTranslation(),
    app = useApp();
  let title = "",
    detail = "",
    route = "";
  switch (card.type) {
    case "chart_fact":
      title = c.bodies[card.body];
      detail = `${degrees(card.degree_in_sign)} ${c.signs[card.sign]} · ${c.houses[String(card.house)]?.ordinal}${card.retrograde && !card.body.endsWith("_node") ? ` · ${c.terms.retrograde}` : ""}`;
      route = "/(tabs)/chart";
      break;
    case "best_days":
      title = c.activities[card.activity];
      detail = card.days
        .map((d) => `${d.date} · ${c.grades[d.grade]}`)
        .join("\n");
      route = `/best-days/${card.activity}?profile=${profile}`;
      break;
    case "place":
      title = card.name;
      detail = card.cards
        .map((item) => `${c.goals[item.goal]} · ${item.band_label}`)
        .join("\n");
      route = `/map/place/${encodeURIComponent(card.place_id)}?profile=${profile}`;
      break;
    case "period":
      title = card.period.label;
      detail = `${card.period.start} – ${card.period.end}`;
      route = `/calendar/item/${encodeURIComponent(card.period.id)}?profile=${profile}`;
      break;
    case "transit":
      title = card.transit.label;
      detail = card.transit.phase_label;
      route = `/calendar/item/${encodeURIComponent(card.transit.id)}?profile=${profile}`;
      break;
    case "compatibility":
      title = card.labels.join(" & ");
      detail = c.compat_types[card.compat_type];
      route = `/match/${card.compatibility_id}`;
      break;
    case "forecast":
      title = card.title;
      route = `/(tabs)/ahead?profile=${profile}&view=${card.horizon}${card.date ? `&date=${card.date}` : ""}${card.month ? `&month=${card.month}` : ""}`;
      break;
  }
  return (
    <Card>
      <Txt>{title}</Txt>
      {!!detail && <Txt muted>{detail}</Txt>}
      <Button
        secondary
        label={t("open")}
        onPress={() => {
          app.update({ activeProfileId: profile });
          router.push(route as never);
        }}
      />
    </Card>
  );
}
