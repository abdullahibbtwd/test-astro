import { space as dsSpace } from "../../design-system/theme/tokens";
import { View } from "react-native";
import { useTranslation } from "react-i18next";
import { Row, Txt } from "../../design/components";
import { Glyph } from "../../design/components/Glyph";
import { AspectGlyph } from "../../design/components/AspectGlyph";
import type { ChartData, Catalogue } from "../../../contracts/spec-types";
import {
  aspectOrder,
  degrees,
  inSign,
  isRetrograde,
  type Selection,
} from "./facts";
export type ChartTab = "reading" | "planets" | "houses" | "aspects";
export function ChartTables({
  chart,
  catalogue: c,
  tab,
  select,
}: {
  chart: ChartData;
  catalogue: Catalogue;
  tab: ChartTab;
  select: (selection: Selection) => void;
}) {
  const { t } = useTranslation();
  if (tab === "planets")
    return (
      <View>
        {chart.points
          .filter((point) => !!c.bodies[point.body])
          .map((point) => (
            <Row
              key={point.body}
              leading={<Glyph name={point.body} />}
              label={c.bodies[point.body]}
              detail={[
                `${degrees(point.degree_in_sign)} ${c.signs[point.sign]}`,
                c.houses[String(point.house)]?.ordinal,
                isRetrograde(point) ? c.terms.retrograde : null,
              ]
                .filter(Boolean)
                .join(" · ")}
              onPress={() => select({ kind: "body", body: point.body })}
            />
          ))}
      </View>
    );
  if (tab === "houses")
    return (
      <View>
        {[...chart.houses]
          .sort((a, b) => a.house - b.house)
          .map((house) => (
            <Row
              key={house.house}
              leading={<Glyph name={house.sign} />}
              label={`${c.houses[String(house.house)]?.ordinal} · ${c.houses[String(house.house)]?.name}`}
              detail={[
                `${degrees(inSign(house.cusp_longitude))} ${c.signs[house.sign]}`,
                `${t("rulers")}: ${house.rulers.map((b) => c.bodies[b]).join(", ")}`,
                `${t("planets")}: ${house.planets.map((b) => c.bodies[b]).join(", ") || t("none")}`,
              ].join("\n")}
              onPress={() => select({ kind: "house", house: house.house })}
            />
          ))}
      </View>
    );
  if (tab === "aspects")
    return (
      <View style={{ gap: dsSpace[6] }}>
        {aspectOrder.map((type) => {
          const items = chart.aspects
            .map((aspect, index) => ({ aspect, index }))
            .filter(({ aspect }) => aspect.type === type);
          return items.length ? (
            <View key={type}>
              <Txt kind="title">{c.aspects[type]}</Txt>
              {items.map(({ aspect, index }) => (
                <Row
                  key={index}
                  leading={<AspectGlyph type={type} />}
                  label={`${c.bodies[aspect.a]} · ${c.bodies[aspect.b]}`}
                  detail={`${t("orb")}: ${degrees(aspect.orb)}`}
                  onPress={() => select({ kind: "aspect", index })}
                />
              ))}
            </View>
          ) : null;
        })}
        {!chart.aspects.length && <Txt muted>{t("noAspects")}</Txt>}
      </View>
    );
  return null;
}
