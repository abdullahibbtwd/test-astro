import { ContentList, type ContentListProps } from "./ContentList";
import { useSnackbarLayout } from "./snackbar-store";
import { useCallback, useEffect, useState } from "react";
import { onlineManager } from "@tanstack/react-query";
import { describeError } from "../../api/errors";
import { ContractError } from "../../api/contract-validation";
import { reportError } from "../../lib/telemetry";
import {
  Pressable,
  Text,
  View,
  TextInput,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  type ScrollViewProps,
  StyleSheet,
  ActivityIndicator,
  type TextInputProps,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Stack, router, useFocusEffect } from "expo-router";
import ArrowLeft from "lucide-react-native/icons/arrow-left";
import ChevronRight from "lucide-react-native/icons/chevron-right";
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
  scrollRef,
  scrollProps,
  embedded = false,
  pinned,
  scroll = true,
  list = false,
  listProps,
  largeTitle = false,
  headerless = false,
}: {
  children: React.ReactNode;
  title?: string;
  back?: boolean;
  footer?: React.ReactNode;
  scrollRef?: React.RefObject<ScrollView | null>;
  scrollProps?: ScrollViewProps;
  embedded?: boolean;
  pinned?: React.ReactNode;
  scroll?: boolean;
  list?: boolean;
  listProps?: ContentListProps;
  largeTitle?: boolean;
  headerless?: boolean;
}) {
  const c = useTheme(),
    { t } = useTranslation();
  const [footerHeight, setFooterHeight] = useState(0);
  useFocusEffect(
    useCallback(() => {
      useSnackbarLayout.setState({ footerHeight });
      return () => useSnackbarLayout.setState({ footerHeight: 0 });
    }, [footerHeight]),
  );
  return (
    <SafeAreaView
      style={{ flex: 1, backgroundColor: c.bg }}
      edges={
        headerless
          ? ["top", "left", "right", "bottom"]
          : embedded
            ? ["left", "right"]
            : ["left", "right", "bottom"]
      }
    >
      {title && !headerless && (
        <Stack.Screen
          options={{
            title,
            headerShown: true,
            headerBackVisible: back,
            headerLargeTitle: largeTitle,
          }}
        />
      )}
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {headerless && back && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("back")}
            onPress={() =>
              router.canGoBack() ? router.back() : router.replace("/")
            }
            style={{
              width: 44,
              height: 44,
              marginLeft: 16,
              justifyContent: "center",
            }}
          >
            <ArrowLeft color={c.ink} size={24} />
          </Pressable>
        )}
        {pinned && (
          <View style={{ paddingHorizontal: 16, paddingVertical: 8, gap: 4 }}>
            {pinned}
          </View>
        )}
        {list ? (
          <ContentList {...listProps}>{children}</ContentList>
        ) : scroll ? (
          <ScrollView
            ref={scrollRef}
            {...scrollProps}
            contentInsetAdjustmentBehavior="automatic"
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={[
              styles.screen,
              scrollProps?.contentContainerStyle,
            ]}
          >
            {children}
          </ScrollView>
        ) : (
          children
        )}
        {footer && (
          <View
            onLayout={(e) => setFooterHeight(e.nativeEvent.layout.height)}
            style={{ padding: 20, borderTopWidth: 1, borderColor: c.hair }}
          >
            {footer}
          </View>
        )}
      </KeyboardAvoidingView>
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
      accessibilityLabel={[label, detail].filter(Boolean).join(", ")}
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
  role = "radio",
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  role?: "radio" | "checkbox" | "button";
  onPress: () => void;
}) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole={role}
      accessibilityLabel={label}
      accessibilityState={role === "button" ? {} : { checked: selected }}
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
export function Choices({
  children,
  multi = false,
}: PropsWithChildren<{ multi?: boolean }>) {
  return (
    <View
      accessibilityRole={multi ? undefined : "radiogroup"}
      style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}
    >
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
  const [online, setOnline] = useState(onlineManager.isOnline());
  const description = describeError(error, online);
  const [remaining, setRemaining] = useState(0);
  useEffect(() => onlineManager.subscribe(setOnline), []);
  useEffect(() => {
    setRemaining(description.retryAfterSec ?? 0);
    const timer = setInterval(
      () => setRemaining((n) => Math.max(0, n - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, [error, description.retryAfterSec]);
  useEffect(() => {
    if (
      error &&
      (description.kind === "invalid" || error instanceof ContractError)
    )
      reportError(error);
  }, [error, description.kind]);
  if (!error || description.kind === "unauthorized") return null;
  return (
    <Card>
      <Txt>{t(description.titleKey)}</Txt>
      {description.action === "back" && (
        <Button secondary label={t("back")} onPress={() => router.back()} />
      )}
      {retry &&
        ["retry", "refresh", "request"].includes(description.action) && (
          <Button
            secondary
            disabled={remaining > 0}
            label={
              remaining > 0
                ? t("retryCountdown", { seconds: remaining })
                : t(
                    description.action === "refresh"
                      ? "refresh"
                      : description.action === "request"
                        ? "requestReading"
                        : "retry",
                  )
            }
            onPress={retry}
          />
        )}
    </Card>
  );
}

export function Skeleton({
  variant = "block",
  lines = 3,
}: {
  variant?: "lines" | "block";
  lines?: number;
}) {
  const { t } = useTranslation();
  const c = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={t("loading")}
      accessibilityState={{ busy: true }}
      style={{ gap: 16 }}
    >
      {Array.from({ length: variant === "lines" ? lines : 1 }, (_, i) => (
        <View
          key={i}
          style={{
            height: variant === "lines" ? 16 : 96,
            width: variant === "lines" && i === lines - 1 ? "60%" : "100%",
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
