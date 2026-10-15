import { useState, type ReactNode } from "react";
import { View, TextInput, Pressable, type TextInputProps } from "react-native";
import { useTheme } from "../ThemeProvider";
import { AppText } from "../text/AppText";
import { Glyph } from "./Glyph";
import {
  size,
  radius,
  space,
  opacity,
  type as typeStyles,
} from "../theme/tokens";
export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <View style={{ gap: space[2] }}>
      <AppText variant="label" color="inkSoft">
        {label}
      </AppText>
      <View style={{ flexDirection: "row", gap: space[2] }}>{children}</View>
      {error ? (
        <View
          accessibilityLiveRegion="polite"
          style={{ flexDirection: "row", gap: space[2], alignItems: "center" }}
        >
          <Glyph name="alert" size={space[4]} color="danger" />
          <AppText variant="caption" color="danger" style={{ flex: 1 }}>
            {error}
          </AppText>
        </View>
      ) : hint ? (
        <AppText variant="caption" color="inkFaint">
          {hint}
        </AppText>
      ) : null}
    </View>
  );
}
export type SelectFieldProps = {
  valueLabel?: string;
  placeholder?: string;
  onPress: () => void;
  invalid?: boolean;
  disabled?: boolean;
  flex?: number;
  accessibilityLabel: string;
};
export function SelectField({
  valueLabel,
  placeholder,
  onPress,
  invalid,
  disabled,
  flex = 1,
  accessibilityLabel,
}: SelectFieldProps) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityLabel={accessibilityLabel}
      accessibilityValue={{ text: valueLabel ?? placeholder }}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled }}
      style={({ pressed }) => ({
        flex,
        minHeight: size.control,
        borderWidth: size.controlBorder,
        borderRadius: radius.md,
        borderColor: invalid
          ? colors.danger
          : pressed
            ? colors.accent
            : colors.borderControl,
        paddingLeft: space[3],
        paddingRight: 36,
        justifyContent: "center",
        opacity: disabled ? opacity.disabled : 1,
      })}
    >
      <AppText
        variant={valueLabel ? "input" : "body"}
        color={valueLabel ? "inkSoft" : "inkFaint"}
        numberOfLines={1}
      >
        {valueLabel ?? placeholder}
      </AppText>
      <View style={{ position: "absolute", right: space[2] }}>
        <Glyph name="chevron-down" size={20} />
      </View>
    </Pressable>
  );
}
export type TextInputFieldProps = {
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  icon?: "map-pin" | "search";
  invalid?: boolean;
} & TextInputProps;
export function TextInputField({
  icon,
  invalid,
  style,
  onFocus,
  onBlur,
  ...props
}: TextInputFieldProps) {
  const { colors } = useTheme(),
    [focused, setFocused] = useState(false);
  const { uppercase: _uppercase, ...font } = typeStyles.input;
  return (
    <View style={{ flex: 1, justifyContent: "center" }}>
      <TextInput
        {...props}
        onFocus={(event) => {
          setFocused(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
        placeholderTextColor={colors.inkFaint}
        selectionColor={colors.accent}
        cursorColor={colors.accent}
        maxFontSizeMultiplier={1.5}
        style={[
          font,
          {
            includeFontPadding: false,
            minHeight: size.control,
            paddingHorizontal: space[4],
            paddingLeft: icon ? 44 : space[4],
            paddingVertical: space[2],
            borderWidth: size.controlBorder,
            borderColor: invalid
              ? colors.danger
              : focused
                ? colors.accent
                : colors.borderControl,
            borderRadius: radius.md,
            color: colors.inkSoft,
          },
          style,
        ]}
      />
      {icon && (
        <View
          pointerEvents="none"
          style={{ position: "absolute", left: space[3] }}
        >
          <Glyph name={icon} size={20} />
        </View>
      )}
    </View>
  );
}
