import type { ReactNode } from "react";
import { Modal, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../ThemeProvider";
import { radius, shadow, size, space } from "../theme/tokens";
import { AppText } from "../text/AppText";
import { Glyph } from "./Glyph";
import { Title } from "./Title";
export function ListRow({
  children,
  onPress,
}: {
  children: string;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={{
        minHeight: size.buttonLg,
        flexDirection: "row",
        alignItems: "center",
        gap: space[3],
        borderBottomWidth: size.controlBorder,
        borderBottomColor: colors.hairline,
      }}
    >
      <AppText style={{ flex: 1 }}>{children}</AppText>
      <Glyph name="chevron-right" />
    </Pressable>
  );
}
export function ChatBubble({
  role,
  children,
}: {
  role: "user" | "assistant";
  children: string;
}) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        alignSelf: role === "user" ? "flex-end" : "flex-start",
        backgroundColor:
          role === "user" ? colors.primary : colors.surfaceRaised,
        borderRadius: radius.md,
        paddingVertical: space[3],
        paddingHorizontal: space[4],
      }}
    >
      <AppText color={role === "user" ? "onPrimary" : "ink"}>
        {children}
      </AppText>
    </View>
  );
}
export function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const { name, colors } = useTheme(),
    safe = useSafeAreaInsets();
  return (
    <Modal
      visible={open}
      transparent
      animationType="none"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View
        style={{
          flex: 1,
          justifyContent: "flex-end",
          backgroundColor: colors.scrim,
        }}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Close preview sheet"
          onPress={onClose}
          style={{ flex: 1 }}
        />
        <View
          accessibilityViewIsModal
          style={{
            backgroundColor: colors.surfaceRaised,
            borderTopLeftRadius: radius.lg,
            borderTopRightRadius: radius.lg,
            padding: space[8],
            paddingBottom: safe.bottom + space[8],
            gap: space[6],
            ...shadow.sheet[name],
          }}
        >
          <Title variant="displaySection">{title}</Title>
          {children}
        </View>
      </View>
    </Modal>
  );
}
