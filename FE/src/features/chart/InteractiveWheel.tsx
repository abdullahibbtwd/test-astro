import Maximize2 from "lucide-react-native/icons/maximize-2";
import RotateCcw from "lucide-react-native/icons/rotate-ccw";
import { IconButton } from "../../design/components/IconButton";
import { ActionSheet } from "../../design/components/ActionSheet";
import { useEffect, useMemo, useState } from "react";
import { View, AccessibilityInfo } from "react-native";
import Animated, {
  runOnJS,
  useSharedValue,
  useAnimatedStyle,
} from "react-native-reanimated";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { SvgCss } from "react-native-svg/css";
import Svg, { Circle, Line, Path } from "react-native-svg";
import { useTranslation } from "react-i18next";
import { computeWheel } from "../../../packages/wheel-core/model";
import { toWheelInput } from "../../../packages/wheel-core/adapter";
import { nativeWheelSvg } from "../../../packages/wheel-core/native-svg";
import { hitTest, touchToModel } from "../../../packages/wheel-core/hit-test";
import { mod360 } from "../../../packages/wheel-core/transform";
import { useTheme } from "../../design/theme";
import { Button } from "../../design/components";
import { AspectGlyph } from "../../design/components/AspectGlyph";
import { degrees, signs, type Selection } from "./facts";
import type { Body, ChartData, Catalogue } from "../../../contracts/spec-types";
const bodyId = (name: string) => name.toLowerCase().replace(/ /g, "_") as Body;
export function InteractiveWheel({
  chart,
  catalogue,
  selection,
  select,
  onExpand,
}: {
  onExpand?: () => void;
  chart: ChartData;
  catalogue: Catalogue;
  selection: Selection | null;
  select: (s: Selection | null) => void;
}) {
  const [zoomed, setZoomed] = useState(false),
    [bodies, setBodies] = useState<string[]>([]);
  const c = useTheme(),
    { t } = useTranslation(),
    [screenReader, setScreenReader] = useState(false),
    [width, setWidth] = useState(335),
    scale = useSharedValue(1),
    baseScale = useSharedValue(1),
    x = useSharedValue(0),
    y = useSharedValue(0),
    baseX = useSharedValue(0),
    baseY = useSharedValue(0);
  useEffect(() => {
    void AccessibilityInfo.isScreenReaderEnabled().then(setScreenReader);
    const sub = AccessibilityInfo.addEventListener(
      "screenReaderChanged",
      setScreenReader,
    );
    return () => sub.remove();
  }, []);
  const model = useMemo(() => computeWheel(toWheelInput(chart)), [chart]),
    xml = useMemo(
      () => nativeWheelSvg(chart, c.bg === "#1A2030" ? "dark" : "light"),
      [chart, c.bg],
    );
  const tap = (
    px: number,
    py: number,
    zoom: number,
    panX: number,
    panY: number,
  ) => {
    const p = touchToModel(px, py, width, zoom, panX, panY),
      hit = hitTest(model, p.x, p.y, width, zoom);
    if (!hit) {
      select(null);
      return;
    }
    if (hit.kind === "body") {
      if (hit.names.length > 1) setBodies(hit.names);
      else select({ kind: "body", body: bodyId(hit.names[0]!) });
    } else if (hit.kind === "sign")
      select({ kind: "sign", sign: signs[hit.index]! });
    else select(hit);
  };
  const pinch = Gesture.Pinch()
    .onStart(() => {
      baseScale.value = scale.value;
    })
    .onUpdate((e) => {
      scale.value = Math.max(1, Math.min(3, baseScale.value * e.scale));
    })
    .onEnd(() => {
      runOnJS(setZoomed)(scale.value > 1);
      const bound = (width * (scale.value - 1)) / 2;
      x.value = Math.max(-bound, Math.min(bound, x.value));
      y.value = Math.max(-bound, Math.min(bound, y.value));
    });
  const pan = Gesture.Pan()
    .enabled(zoomed)
    .minPointers(1)
    .minDistance(8)
    .onStart(() => {
      baseX.value = x.value;
      baseY.value = y.value;
    })
    .onUpdate((e) => {
      if (scale.value <= 1) return;
      const bound = (width * (scale.value - 1)) / 2;
      x.value = Math.max(-bound, Math.min(bound, baseX.value + e.translationX));
      y.value = Math.max(-bound, Math.min(bound, baseY.value + e.translationY));
    });
  const doubleTap = Gesture.Tap()
    .numberOfTaps(2)
    .runOnJS(true)
    .onEnd(() => {
      const next = scale.value > 1 ? 1 : 2;
      scale.value = next;
      x.value = 0;
      y.value = 0;
      setZoomed(next > 1);
    });
  const press = Gesture.Tap()
    .runOnJS(true)
    .onEnd((e) => tap(e.x, e.y, scale.value, x.value, y.value));
  const animated = useAnimatedStyle(() => ({
    transform: [
      { translateX: x.value },
      { translateY: y.value },
      { scale: scale.value },
    ],
  }));
  const selectedBodies = chart.points
    .filter((p) =>
      selection?.kind === "body"
        ? p.body === selection.body
        : selection?.kind === "sign"
          ? p.sign === selection.sign
          : selection?.kind === "house"
            ? p.house === selection.house
            : selection?.kind === "aspect"
              ? [
                  chart.aspects[selection.index]?.a,
                  chart.aspects[selection.index]?.b,
                ].includes(p.body)
              : false,
    )
    .map((p) => p.body);
  let wedge: string | undefined;
  if (selection?.kind === "sign" || selection?.kind === "house") {
    const start =
        selection.kind === "sign"
          ? signs.indexOf(selection.sign) * 30
          : chart.houses[selection.house - 1]!.cusp_longitude,
      end =
        selection.kind === "sign"
          ? start + 30
          : chart.houses[selection.house % 12]!.cusp_longitude,
      r = selection.kind === "sign" ? 460 : 396,
      a = model.point(start, r),
      b = model.point(end, r);
    if (selection.kind === "sign") {
      const innerA = model.point(start, 396),
        innerB = model.point(end, 396);
      wedge = `M${innerA.x} ${innerA.y} L${a.x} ${a.y} A${r} ${r} 0 0 0 ${b.x} ${b.y} L${innerB.x} ${innerB.y} A396 396 0 0 1 ${innerA.x} ${innerA.y} Z`;
    } else
      wedge = `M500 500 L${a.x} ${a.y} A${r} ${r} 0 ${mod360(end - start) > 180 ? 1 : 0} 0 ${b.x} ${b.y} Z`;
  }
  return (
    <>
      <View
        onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
        style={{ width: "100%", aspectRatio: 1, overflow: "hidden" }}
        accessibilityLabel={t("chartWheel")}
        accessibilityHint={t("chartWheelHint")}
      >
        <GestureDetector
          gesture={Gesture.Simultaneous(
            pinch,
            Gesture.Race(pan, Gesture.Exclusive(doubleTap, press)),
          )}
        >
          <Animated.View style={[{ width, height: width }, animated]}>
            <SvgCss
              xml={
                selection
                  ? xml.replace(/<line[^>]*class="cw-aspect"[^>]*>/g, (line) =>
                      line.replace(
                        /stroke-opacity="[^"]*"/,
                        'stroke-opacity="0.15"',
                      ),
                    )
                  : xml
              }
              width={width}
              height={width}
            />
            <Svg
              pointerEvents="none"
              style={{ position: "absolute", top: 0, left: 0 }}
              width={width}
              height={width}
              viewBox="0 0 1000 1000"
            >
              {wedge && <Path d={wedge} fill={c.accent} opacity={0.12} />}
              {selection &&
                model.chords
                  .filter((chord, index) =>
                    selection.kind === "aspect"
                      ? selection.index === index
                      : selectedBodies.includes(bodyId(chord.rel.source)) ||
                        selectedBodies.includes(bodyId(chord.rel.target)),
                  )
                  .map((chord, index) => (
                    <Line
                      key={index}
                      x1={chord.a.x}
                      y1={chord.a.y}
                      x2={chord.b.x}
                      y2={chord.b.y}
                      stroke={c.accent}
                      strokeWidth={3}
                    />
                  ))}
              {model.points
                .filter((p) => selectedBodies.includes(bodyId(p.name)))
                .map((p) => (
                  <Circle
                    key={p.name}
                    cx={p.glyph.x}
                    cy={p.glyph.y}
                    r={25}
                    stroke={c.accent}
                    strokeWidth={3}
                    fill="none"
                  />
                ))}
              {selection?.kind === "axis" &&
                model.axes
                  .filter((a) => a.axis === selection.axis)
                  .map((a) => (
                    <Line
                      key={a.axis}
                      x1={a.a.x}
                      y1={a.a.y}
                      x2={a.b.x}
                      y2={a.b.y}
                      stroke={c.accent}
                      strokeWidth={3}
                    />
                  ))}
            </Svg>
            {selection?.kind === "aspect" &&
              model.chords[selection.index] &&
              (() => {
                const chord = model.chords[selection.index]!;
                return (
                  <View
                    pointerEvents="none"
                    style={{
                      position: "absolute",
                      left: (((chord.a.x + chord.b.x) / 2) * width) / 1000 - 10,
                      top: (((chord.a.y + chord.b.y) / 2) * width) / 1000 - 10,
                      backgroundColor: c.bg,
                      borderRadius: 10,
                    }}
                  >
                    <AspectGlyph
                      type={chart.aspects[selection.index]!.type}
                      size={20}
                    />
                  </View>
                );
              })()}
          </Animated.View>
        </GestureDetector>
        <View
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            backgroundColor: c.surface,
            borderRadius: 22,
          }}
        >
          {onExpand && (
            <IconButton
              accessibilityLabel={t("focusMode")}
              icon={<Maximize2 size={20} color={c.ink} />}
              onPress={onExpand}
            />
          )}
          {zoomed && (
            <IconButton
              accessibilityLabel={t("resetZoom")}
              icon={<RotateCcw size={20} color={c.ink} />}
              onPress={() => {
                scale.value = 1;
                x.value = 0;
                y.value = 0;
                setZoomed(false);
              }}
            />
          )}
        </View>
      </View>
      <ActionSheet
        open={bodies.length > 0}
        title={t("choosePlanet")}
        onClose={() => setBodies([])}
        actions={bodies.map((name) => ({
          label: catalogue.bodies[bodyId(name)],
          onPress: () => select({ kind: "body", body: bodyId(name) }),
        }))}
      />
      {screenReader && (
        <View style={{ gap: 8 }}>
          {chart.points.map((p) => (
            <Button
              key={p.body}
              secondary
              label={`${catalogue.bodies[p.body]}, ${degrees(p.degree_in_sign)} ${catalogue.signs[p.sign]}, ${catalogue.houses[String(p.house)]?.ordinal}`}
              onPress={() => select({ kind: "body", body: p.body })}
            />
          ))}
        </View>
      )}
    </>
  );
}
