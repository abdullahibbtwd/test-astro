import {
  Pressable,
  Text,
  View,
  TextInput,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  type TextInputProps,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ArrowLeft, ChevronRight } from "lucide-react-native";
import { useTranslation } from "react-i18next";
import { useTheme } from "../theme";
import type { PropsWithChildren } from "react";
export function Txt({
  children,
  kind = "body",
  muted = false,
  style,
  numberOfLines,
}: {
  children: React.ReactNode;
  kind?: "body" | "title" | "display" | "caption" | "reading";
  muted?: boolean;
  style?: any;
  numberOfLines?: number;
}) {
  const c = useTheme();
  return (
    <Text
      numberOfLines={numberOfLines}
      selectable={kind === "reading"}
      maxFontSizeMultiplier={kind === "reading" ? 2 : 1.6}
      style={[
        {
          color: muted ? c.ink2 : c.ink,
          fontFamily:
            kind === "reading"
              ? "SourceSerif4"
              : kind === "title" || kind === "display"
                ? "Inter-SemiBold"
                : "Inter",
          fontSize:
            kind === "display"
              ? 32
              : kind === "title"
                ? 24
                : kind === "caption"
                  ? 13
                  : kind === "reading"
                    ? 18
                    : 16,
          lineHeight:
            kind === "display"
              ? 40
              : kind === "title"
                ? 32
                : kind === "caption"
                  ? 20
                  : kind === "reading"
                    ? 29
                    : 24,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}
export function Screen({
  children,
  title,
  back = false,
  footer,
}: {
  children: React.ReactNode;
  title?: string;
  back?: boolean;
  footer?: React.ReactNode;
}) {
  const c = useTheme(),
    { t } = useTranslation();
  return (
    <SafeAreaView
      style={{ flex: 1, backgroundColor: c.bg }}
      edges={["top", "left", "right", "bottom"]}
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.screen}
      >
        {back && (
          <Pressable
            accessibilityLabel={t("back")}
            accessibilityRole="button"
            onPress={() =>
              router.canGoBack() ? router.back() : router.replace("/")
            }
            style={{
              minHeight: 44,
              justifyContent: "center",
              alignSelf: "flex-start",
            }}
          >
            <ArrowLeft color={c.ink} size={24} />
          </Pressable>
        )}
        {title && <Txt kind="title">{title}</Txt>}
        {children}
      </ScrollView>
      {footer && (
        <View style={{ padding: 20, borderTopWidth: 1, borderColor: c.hair }}>
          {footer}
        </View>
      )}
    </SafeAreaView>
  );
}
export function Button({
  label,
  onPress,
  secondary = false,
  danger = false,
  disabled = false,
  loading = false,
}: {
  label: string;
  onPress: () => void;
  secondary?: boolean;
  danger?: boolean;
  disabled?: boolean;
  loading?: boolean;
}) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || loading, busy: loading }}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        {
          minHeight: 52,
          padding: 14,
          borderRadius: 12,
          alignItems: "center",
          justifyContent: "center",
          borderWidth: 1,
          borderColor: danger ? c.danger : c.accent,
          backgroundColor: secondary ? c.bg : danger ? c.danger : c.accent,
          opacity: disabled ? 0.4 : pressed ? 0.75 : 1,
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={secondary ? c.accent : c.onAccent} />
      ) : (
        <Txt
          style={{
            color: secondary ? (danger ? c.danger : c.accent) : c.onAccent,
            fontFamily: "Inter-SemiBold",
          }}
        >
          {label}
        </Txt>
      )}
    </Pressable>
  );
}
export function Card({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
}) {
  const c = useTheme();
  return (
    <View
      style={[
        {
          padding: 20,
          gap: 12,
          borderWidth: 1,
          borderColor: c.hair,
          borderRadius: 16,
          backgroundColor: c.surface,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}
export function Row({
  leading,
  label,
  detail,
  onPress,
  onLongPress,
}: {
  leading?: React.ReactNode;
  label: string;
  detail?: string;
  onPress?: () => void;
  onLongPress?: () => void;
}) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole={onPress ? "button" : undefined}
      disabled={!onPress && !onLongPress}
      onPress={onPress}
      onLongPress={onLongPress}
      style={{
        minHeight: 64,
        paddingVertical: 16,
        borderBottomWidth: 1,
        borderColor: c.hair,
        flexDirection: "row",
        gap: 12,
        alignItems: "center",
      }}
    >
      {leading && (
        <View
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: c.accentSoft,
          }}
        >
          {leading}
        </View>
      )}
      <View style={{ flex: 1, gap: 4 }}>
        <Txt>{label}</Txt>
        {detail && (
          <Txt kind="caption" muted>
            {detail}
          </Txt>
        )}
      </View>
      {onPress && <ChevronRight color={c.ink2} size={20} />}
    </Pressable>
  );
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  const c = useTheme();
  return (
    <View style={{ gap: 8 }}>
      <Txt kind="caption">{label}</Txt>
      <TextInput
        {...props}
        accessibilityLabel={label}
        placeholderTextColor={c.ink3}
        maxFontSizeMultiplier={1.6}
        style={[
          {
            minHeight: 52,
            padding: 16,
            borderWidth: 1,
            borderColor: c.hair,
            borderRadius: 12,
            color: c.ink,
            backgroundColor: c.surfaceAlt,
            fontFamily: "Inter",
            fontSize: 16,
          },
          props.style,
        ]}
      />
    </View>
  );
}
export function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={{
        minHeight: 44,
        paddingHorizontal: 16,
        paddingVertical: 12,
        borderRadius: 30,
        borderWidth: 1,
        borderColor: selected ? c.accent : c.hair,
        backgroundColor: selected ? c.accentSoft : c.surface,
      }}
    >
      <Txt style={{ color: selected ? c.accent : c.ink }}>{label}</Txt>
    </Pressable>
  );
}
export function Choices({ children }: PropsWithChildren) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {children}
    </View>
  );
}
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  const { t } = useTranslation();
  return error ? (
    <Card>
      <Txt>{t("error")}</Txt>
      {retry && <Button secondary label={t("retry")} onPress={retry} />}
    </Card>
  ) : null;
}
export function Skeleton() {
  const c = useTheme();
  return (
    <View accessible accessibilityLabel="Loading" style={{ gap: 16 }}>
      {[1, 2, 3].map((i) => (
        <View
          key={i}
          style={{
            height: 64,
            borderRadius: 12,
            backgroundColor: c.surfaceAlt,
          }}
        />
      ))}
    </View>
  );
}
export function Progress({ step, total }: { step: number; total: number }) {
  const c = useTheme();
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: total, now: step }}
      style={{ height: 3, backgroundColor: c.hair }}
    >
      <View
        style={{
          height: 3,
          width: `${(step / total) * 100}%`,
          backgroundColor: c.accent,
        }}
      />
    </View>
  );
}
const styles = StyleSheet.create({
  screen: {
    flexGrow: 1,
    padding: 20,
    gap: 24,
    width: "100%",
    maxWidth: 680,
    alignSelf: "center",
  },
});
