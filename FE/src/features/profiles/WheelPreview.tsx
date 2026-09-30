import { useMemo } from "react";
import { View, useWindowDimensions } from "react-native";
import { SvgCss } from "react-native-svg/css";
import { useTranslation } from "react-i18next";
import { nativeWheelSvg } from "../../../packages/wheel-core/native-svg";
import { useChart } from "../../api/hooks";
import { useTheme } from "../../design/theme";
import { ErrorNotice, Skeleton } from "../../design/components";
export function WheelPreview({
  id,
  chartKey,
}: {
  id: string;
  chartKey?: string;
}) {
  const chart = useChart(id, chartKey),
    c = useTheme(),
    { width } = useWindowDimensions(),
    { t } = useTranslation();
  const theme = c.bg === "#1A2030" ? "dark" : "light";
  const xml = useMemo(
    () => (chart.data ? nativeWheelSvg(chart.data, theme) : null),
    [chart.data, theme],
  );
  if (chart.isPending) return <Skeleton />;
  if (!xml)
    return (
      <ErrorNotice error={chart.error} retry={() => void chart.refetch()} />
    );
  return (
    <View accessible accessibilityRole="image" accessibilityLabel={t("chart")}>
      <SvgCss xml={xml} width="100%" height={Math.min(width - 40, 480)} />
    </View>
  );
}
