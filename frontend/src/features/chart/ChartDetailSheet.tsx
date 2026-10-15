import { space as dsSpace } from "../../design-system/theme/tokens";
import { useFlags } from "../../lib/flags";
import { View } from "react-native";
import { Sheet } from "../../design/components/Sheet";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Txt, Row, Button, Choices, Chip } from "../../design/components";
import { Glyph } from "../../design/components/Glyph";
import { AspectGlyph } from "../../design/components/AspectGlyph";
import { useGenerated } from "../../api/jobs";
import type {
  ChartData,
  Catalogue,
  NatalReading,
  Body,
  ChartElements,
} from "../../../contracts/spec-types";
import {
  degrees,
  inSign,
  isRetrograde,
  axisPoint,
  readingSections,
  type Selection,
} from "./facts";
export function ChartDetailSheet({
  chart,
  catalogue: c,
  selection,
  select,
  close,
}: {
  chart: ChartData;
  catalogue: Catalogue;
  selection: Selection;
  select: (value: Selection) => void;
  close: () => void;
}) {
  const { t } = useTranslation();
  const reading = useGenerated<NatalReading>(
    ["natal", chart.profile_id, chart.chart_key],
    `/profiles/${chart.profile_id}/natal-reading`,
    "NatalReading",
    false, // Detail selection only reads an already cached natal reading.
  );
  const flags = useFlags();
  const elements = useGenerated<ChartElements>(
    ["elements", chart.profile_id, chart.chart_key],
    `/profiles/${chart.profile_id}/chart/elements`,
    "ChartElements",
    !!flags.elementNotes,
  );
  const point =
    selection.kind === "body"
      ? chart.points.find((p) => p.body === selection.body)
      : undefined;
  const house =
    selection.kind === "house"
      ? chart.houses.find((h) => h.house === selection.house)
      : undefined;
  const aspect =
    selection.kind === "aspect" ? chart.aspects[selection.index] : undefined;
  const axis =
    selection.kind === "axis" ? axisPoint(chart, selection.axis) : undefined;
  const note = elements.data
    ? selection.kind === "body"
      ? elements.data.bodies[selection.body]
      : selection.kind === "sign"
        ? elements.data.signs[selection.sign]
        : selection.kind === "house"
          ? elements.data.houses[
              String(selection.house) as keyof ChartElements["houses"]
            ]
          : aspect
            ? elements.data.aspects.find(
                (a) =>
                  a.a === aspect.a &&
                  a.b === aspect.b &&
                  a.type === aspect.type,
              )?.note
            : undefined
    : undefined;
  const title = point
    ? c.bodies[point.body]
    : house
      ? `${c.houses[String(house.house)]?.ordinal} · ${c.houses[String(house.house)]?.name}`
      : aspect
        ? c.aspects[aspect.type]
        : selection.kind === "sign"
          ? c.signs[selection.sign]
          : selection.kind === "axis"
            ? (c.angles[selection.axis]?.name ?? "")
            : t("chartDetails");
  const bodyChip = (body: Body) => (
    <Chip role="button"
      key={body}
      label={c.bodies[body]}
      selected={false}
      onPress={() => select({ kind: "body", body })}
    />
  );
  const sections = reading.data
    ? readingSections(chart, reading.data, selection)
    : [];
  const openSection = (key: string) => {
    close();
    router.push(`/chart/section/${key}?profile=${chart.profile_id}`);
  };
  return (
    <Sheet open title={title} onClose={close}>
      {point && (
        <>
          <Glyph name={point.body} size={40} />
          <Choices>
            <Chip role="button"
              label={`${degrees(point.degree_in_sign)} ${c.signs[point.sign]}`}
              selected={false}
              onPress={() => select({ kind: "sign", sign: point.sign })}
            />
            <Chip role="button"
              label={
                c.houses[String(point.house)]?.ordinal ?? String(point.house)
              }
              selected={false}
              onPress={() => select({ kind: "house", house: point.house })}
            />
          </Choices>
          {isRetrograde(point) && <Txt>{c.terms.retrograde}</Txt>}
          <Txt kind="title">{t("aspects")}</Txt>
          {chart.aspects.map((a, index) =>
            a.a === point.body || a.b === point.body ? (
              <Row
                key={index}
                leading={<AspectGlyph type={a.type} />}
                label={`${c.bodies[a.a === point.body ? a.b : a.a]} · ${c.aspects[a.type]}`}
                detail={`${t("orb")}: ${degrees(a.orb)}`}
                onPress={() => select({ kind: "aspect", index })}
              />
            ) : null,
          )}
        </>
      )}
      {house && (
        <>
          <Chip role="button"
            label={`${t("cusp")}: ${degrees(inSign(house.cusp_longitude))} ${c.signs[house.sign]}`}
            selected={false}
            onPress={() => select({ kind: "sign", sign: house.sign })}
          />
          <Txt>{t("rulers")}</Txt>
          <Choices>{house.rulers.map(bodyChip)}</Choices>
          <Txt>{t("planets")}</Txt>
          <Choices>
            {house.planets.length ? (
              house.planets.map(bodyChip)
            ) : (
              <Txt muted>{t("none")}</Txt>
            )}
          </Choices>
        </>
      )}
      {selection.kind === "sign" && (
        <>
          <Glyph name={selection.sign} size={40} />
          <Txt>{t("planets")}</Txt>
          <Choices>
            {chart.points
              .filter((p) => p.sign === selection.sign)
              .map((p) => bodyChip(p.body))}
          </Choices>
          {!chart.points.some((p) => p.sign === selection.sign) && (
            <Txt muted>{t("noPlanets")}</Txt>
          )}
          <Txt>{t("houses")}</Txt>
          <Choices>
            {chart.houses
              .filter((h) => h.sign === selection.sign)
              .map((h) => (
                <Chip role="button"
                  key={h.house}
                  label={c.houses[String(h.house)]?.ordinal ?? String(h.house)}
                  selected={false}
                  onPress={() => select({ kind: "house", house: h.house })}
                />
              ))}
          </Choices>
        </>
      )}
      {aspect && (
        <>
          <AspectGlyph type={aspect.type} size={40} />
          <Choices>{[aspect.a, aspect.b].map(bodyChip)}</Choices>
          <Txt>
            {t("orb")}: {degrees(aspect.orb)}
          </Txt>
        </>
      )}
      {axis && (
        <Chip role="button"
          label={`${degrees(axis.degree_in_sign)} ${c.signs[axis.sign]}`}
          selected={false}
          onPress={() => select({ kind: "sign", sign: axis.sign })}
        />
      )}
      {flags.elementNotes && note && <Txt kind="reading">{note.text}</Txt>}
      {!!sections.length && <Txt kind="title">{t("relatedReading")}</Txt>}
      {sections.map((section) => (
        <View key={section.key} style={{ gap: dsSpace[3] }}>
          <Row label={section.title} onPress={() => openSection(section.key)} />
          <Txt
            kind="reading"
            numberOfLines={selection.kind === "house" ? undefined : 2}
          >
            {section.text}
          </Txt>
        </View>
      ))}
      {!reading.data && (
        <>
          <Txt muted>{t("readingUnavailable")}</Txt>
          <Button
            secondary
            label={t("openReading")}
            onPress={() => {
              close();
              router.push(`/chart/reading?profile=${chart.profile_id}`);
            }}
          />
        </>
      )}
    </Sheet>
  );
}
