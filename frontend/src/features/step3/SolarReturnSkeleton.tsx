import { useMemo, useState } from "react";
import { TextInput, useWindowDimensions, View } from "react-native";
import { SvgCss } from "react-native-svg/css";
import {
  Screen,
  Txt,
  Button,
  Choices,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useTheme } from "../../design/theme";
import { nativeWheelSvg } from "../../../packages/wheel-core/native-svg";
import { PendingAstrologerBanner } from "./PendingAstrologerBanner";
import {
  SOLAR_RETURN_PLACEHOLDER,
} from "./placeholders";
import type { SolarReturnSkeletonModel } from "./math";

export type SkeletonStatus = "idle" | "loading" | "ready" | "error";

export function SolarReturnSkeleton({
  year,
  onYearChange,
  status,
  model,
  error,
  onRetry,
  title = "Solar Return",
}: {
  year: number;
  onYearChange: (year: number) => void;
  status: SkeletonStatus;
  model: SolarReturnSkeletonModel | null;
  error?: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const c = useTheme(),
    { width } = useWindowDimensions(),
    [draft, setDraft] = useState(String(year));
  const xml = useMemo(
    () =>
      model?.chart
        ? nativeWheelSvg(model.chart, c.dark ? "dark" : "light")
        : null,
    [model?.chart, c.dark],
  );
  const years = [new Date().getFullYear(), new Date().getFullYear() + 1];
  return (
    <Screen back title={`${title} ${year}`}>
      <PendingAstrologerBanner detail={SOLAR_RETURN_PLACEHOLDER} />
      <Txt kind="caption">Year</Txt>
      <TextInput
        testID="solar-return-year-input"
        accessibilityLabel="Solar return year"
        keyboardType="number-pad"
        value={draft}
        onChangeText={setDraft}
        onEndEditing={() => {
          const next = Number.parseInt(draft, 10);
          if (Number.isFinite(next) && next >= 1900 && next <= 2100)
            onYearChange(next);
          else setDraft(String(year));
        }}
        style={{
          borderWidth: 1,
          borderColor: c.borderControl,
          borderRadius: 8,
          paddingHorizontal: 12,
          paddingVertical: 10,
          color: c.ink,
          minHeight: 44,
        }}
      />
      <Choices>
        {years.map((value) => (
          <Button
            key={value}
            secondary
            label={String(value)}
            onPress={() => {
              setDraft(String(value));
              onYearChange(value);
            }}
          />
        ))}
      </Choices>
      {status === "loading" && (
        <View testID="solar-return-loading">
          <Skeleton />
        </View>
      )}
      {status === "ready" && model && (
        <View testID="solar-return-ready" style={{ gap: 12 }}>
          <Txt>
            Return UTC: {model.return_utc}
            {model.place_label ? ` · ${model.place_label}` : ""}
          </Txt>
          <Txt kind="caption">
            Math: {model.math.moment} → {model.math.chart}
          </Txt>
          {xml && (
            <SvgCss
              xml={xml}
              width="100%"
              height={Math.min(width - 40, 480)}
            />
          )}
          <Txt kind="title">Interpretation</Txt>
          <View testID="solar-return-placeholder">
            <Txt kind="reading">{model.interpretation}</Txt>
          </View>
        </View>
      )}
      {status === "error" && (
        <View testID="solar-return-error">
          <ErrorNotice
            error={error ?? new Error("Solar return failed")}
            retry={onRetry}
          />
        </View>
      )}
    </Screen>
  );
}
