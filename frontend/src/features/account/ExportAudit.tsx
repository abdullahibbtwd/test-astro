import { useRef, useState } from "react";
import { View, Text } from "react-native";
import { SvgCss } from "react-native-svg/css";
import { captureRef } from "react-native-view-shot";
import { File, Paths } from "expo-file-system";
import { useProfile } from "../shared/useProfile";
import { useChart } from "../../api/hooks";
import { Screen, Button, Txt, ErrorNotice } from "../../design/components";
import { nativeWheelSvg } from "../../../packages/wheel-core/native-svg";
import { renderChartImage } from "../exports/native";
export function ExportAudit() {
  const { id, profile } = useProfile(),
    chart = useChart(id, profile?.chart_key),
    view = useRef<View>(null),
    [status, setStatus] = useState(""),
    [error, setError] = useState<unknown>();
  const caption = ["Export comparison", "Identical chart · 2048 × 2400"];
  const run = async () => {
    try {
      if (!chart.data) return;
      await renderChartImage(chart.data, caption, false, "png", "fx-skia");
      const uri = await captureRef(view, {
        format: "png",
        quality: 1,
        width: 2048,
        height: 2400,
      });
      const target = new File(Paths.cache, "fx-viewshot.png");
      if (target.exists) target.delete();
      new File(uri).copy(target);
      setStatus("Both 2048 × 2400 images saved to app cache");
    } catch (e) {
      setError(e);
    }
  };
  return (
    <Screen back title="Export comparison">
      <Button
        label="Compare exports"
        disabled={!chart.data}
        onPress={() => {
          void run();
        }}
      />
      <Txt>{status}</Txt>
      <ErrorNotice error={error} />
      {chart.data && (
        <View
          ref={view}
          collapsable={false}
          style={{ width: 320, height: 375, backgroundColor: "#FAFAF8" }}
        >
          <SvgCss
            xml={nativeWheelSvg(chart.data, "light")}
            width={320}
            height={320}
          />
          {caption.map((line, i) => (
            <Text
              key={line}
              style={{
                position: "absolute",
                top: ((2110 + i * 68 - 40) * 320) / 2048,
                width: 320,
                textAlign: "center",
                fontFamily: "Inter",
                fontSize: (40 * 320) / 2048,
                color: "#232A38",
              }}
            >
              {line}
            </Text>
          ))}
        </View>
      )}
    </Screen>
  );
}
