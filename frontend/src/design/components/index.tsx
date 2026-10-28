import { ArrowLeft, ChevronRight } from "../../design-system/LegacyIcons";
import { AppText } from "../../design-system/text/AppText";
import { size as dsSize, space as dsSpace, radius as dsRadius, opacity as dsOpacity } from "../../design-system/theme/tokens";
import { TextInputField } from "../../design-system/components/Fields";
import { ScreenBackdrop } from "../../design-system/components/ScreenBackdrop";
import { ContentList, type ContentListProps } from "./ContentList";
import { useSnackbarLayout } from "./snackbar-store";
import { useCallback, useEffect, useState } from "react";
import { onlineManager } from "@tanstack/react-query";
import { describeError } from "../../api/errors";
import { ContractError } from "../../api/contract-validation";
import { reportError } from "../../lib/telemetry";
import {
  Pressable,
  View,
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


import { useTranslation } from "react-i18next";
import { useTheme } from "../theme";
import type { PropsWithChildren } from "react";
export function Txt({
  children,
  kind = "body",
  muted = false,
  style,
  numberOfLines,
  adjustsFontSizeToFit,
  minimumFontScale,
}: {
  children: React.ReactNode;
  kind?: "body" | "title" | "display" | "caption" | "reading";
  muted?: boolean;
  style?: any;
  numberOfLines?: number;
  adjustsFontSizeToFit?: boolean;
  minimumFontScale?: number;
}) {
  const c = useTheme();
  const variant = kind === "reading" ? "bodyLg" : kind === "title" ? "displaySection" : kind === "display" ? "displayTitle" : kind === "caption" ? "caption" : "body";
  const content = Array.isArray(children) && children.every(child => typeof child === "string" || typeof child === "number") ? children.join("") : typeof children === "number" ? String(children) : children;
  return <AppText variant={variant} color={muted ? "inkSoft" : kind === "title" || kind === "display" ? "accent" : "ink"}
    accessibilityRole={kind === "title" || kind === "display" ? "header" : undefined}
    selectable={kind === "reading"} numberOfLines={numberOfLines}
    adjustsFontSizeToFit={adjustsFontSizeToFit} minimumFontScale={minimumFontScale}
    style={[{ color: muted ? c.ink2 : kind === "title" || kind === "display" ? c.accent : c.ink }, style]}>{content}</AppText>;
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
  arch = false,
  grain = false,
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
  arch?: boolean;
  grain?: boolean;
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
      <ScreenBackdrop arch={arch} grain={grain} />
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
              marginLeft: dsSpace[4],
              justifyContent: "center",
            }}
          >
            <ArrowLeft color={c.ink} size={24} />
          </Pressable>
        )}
        {pinned && (
          <View style={{ paddingHorizontal: dsSpace[4], paddingVertical: dsSpace[2], gap: dsSpace[1] }}>
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
              arch && { paddingHorizontal: dsSize.screenPaddingX + dsSize.archInset },
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
      accessibilityLabel={label}
      accessibilityState={{ disabled: disabled || loading, busy: loading }}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        {
          alignSelf: "stretch",
          minHeight: dsSize.buttonLg,
          paddingHorizontal: dsSpace[6],
          paddingVertical: dsSpace[2],
          borderRadius: dsRadius.md,
          alignItems: "center",
          justifyContent: "center",
          borderWidth: 1,
          borderColor: danger ? c.danger : secondary ? c.borderControl : c.primary,
          backgroundColor: secondary ? undefined : danger ? c.danger : c.primary,
          opacity: disabled || loading ? dsOpacity.disabled : pressed ? .88 : 1,
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={secondary ? c.accent : c.onAccent} />
      ) : (
        <AppText
          variant="button"
          align="center"
          color={secondary ? (danger ? "danger" : "accent") : "onPrimary"}
          numberOfLines={1}
          style={{ flexShrink: 0 }}
        >
          {label}
        </AppText>
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
          padding: dsSpace[6],
          gap: dsSpace[3],
          borderWidth: 1,
          borderColor: c.hair,
          borderRadius: dsRadius.card,
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
        minHeight: dsSize.buttonLg,
        paddingVertical: dsSpace[4],
        borderBottomWidth: 1,
        borderColor: c.hair,
        flexDirection: "row",
        gap: dsSpace[3],
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
      <View style={{ flex: 1, gap: dsSpace[1] }}>
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
  return <View style={{ gap: dsSpace[2] }}><AppText variant="label" color="inkSoft">{label}</AppText><View style={{ flexDirection: "row" }}><TextInputField {...props} value={props.value ?? ""} onChangeText={props.onChangeText ?? (() => {})} accessibilityLabel={label} /></View></View>;
}

export function Chip({
  role = "radio",
  label,
  selected,
  onPress,
  compact = false,
}: {
  label: string;
  selected: boolean;
  role?: "radio" | "checkbox" | "button";
  onPress: () => void;
  /** Tighter padding for dense filter rows on narrow screens. */
  compact?: boolean;
}) {
  const c = useTheme();
  return (
    <Pressable
      accessibilityRole={role}
      accessibilityLabel={label}
      accessibilityState={role === "button" ? {} : { checked: selected }}
      onPress={onPress}
      style={{
        minHeight: compact ? dsSize.buttonMd : 44,
        maxWidth: "100%",
        paddingHorizontal: compact ? dsSpace[3] : dsSpace[4],
        paddingVertical: compact ? dsSpace[2] : dsSpace[3],
        borderRadius: dsRadius.md,
        borderWidth: 1,
        borderColor: selected ? c.primary : c.borderControl,
        backgroundColor: selected ? c.primary : undefined,
        justifyContent: "center",
      }}
    >
      <Txt
        kind={compact ? "caption" : undefined}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.8}
        style={{ color: selected ? c.onPrimary : c.ink }}
      >
        {label}
      </Txt>
    </Pressable>
  );
}
export function Choices({
  children,
  multi = false,
  gap = dsSpace[2],
}: PropsWithChildren<{ multi?: boolean; gap?: number }>) {
  return (
    <View
      accessibilityRole={multi ? undefined : "radiogroup"}
      style={{ flexDirection: "row", flexWrap: "wrap", gap }}
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
      <Txt>
        {description.message ||
          (description.titleKey ? t(description.titleKey) : "")}
      </Txt>
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
      style={{ gap: dsSpace[4] }}
    >
      {Array.from({ length: variant === "lines" ? lines : 1 }, (_, i) => (
        <View
          key={i}
          style={{
            height: variant === "lines" ? 16 : 96,
            width: variant === "lines" && i === lines - 1 ? "60%" : "100%",
            borderRadius: dsRadius.md,
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
      accessible
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
    paddingHorizontal: dsSize.screenPaddingX,
    paddingTop: dsSize.screenPaddingTop,
    paddingBottom: dsSpace[8],
    gap: dsSpace[6],
    width: "100%",
    maxWidth: 680,
    alignSelf: "center",
  },
});
