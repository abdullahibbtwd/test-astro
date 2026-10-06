import { space as dsSpace } from "../../design-system/theme/tokens";
import type { ReactNode } from "react";
import { Pressable, View } from "react-native";
import { Txt } from ".";
import { Sheet } from "./Sheet";
import { useTheme } from "../theme";
export type SheetAction = {
  label: string;
  onPress: () => void;
  icon?: ReactNode;
  destructive?: boolean;
};
export function ActionSheet({
  open,
  title,
  actions,
  onClose,
}: {
  open: boolean;
  title: string;
  actions: SheetAction[];
  onClose: () => void;
}) {
  const c = useTheme();
  return (
    <Sheet open={open} title={title} onClose={onClose}>
      {actions.map((action, i) => (
        <Pressable
          key={i}
          accessibilityRole="button"
          accessibilityLabel={action.label}
          onPress={() => {
            onClose();
            action.onPress();
          }}
          style={{
            minHeight: 52,
            flexDirection: "row",
            alignItems: "center",
            gap: dsSpace[3],
          }}
        >
          <View>{action.icon}</View>
          <Txt style={{ color: action.destructive ? c.danger : c.ink }}>
            {action.label}
          </Txt>
        </Pressable>
      ))}
    </Sheet>
  );
}
