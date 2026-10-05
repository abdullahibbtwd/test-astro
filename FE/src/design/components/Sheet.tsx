import { radius as dsRadius } from "../../design-system/theme/tokens";
import { shadow as dsShadow } from "../../design-system/theme/tokens";
import { space as dsSpace } from "../../design-system/theme/tokens";
import { X } from "../../design-system/LegacyIcons";
import { ContentList } from "./ContentList";
import { useEffect, useRef, type ReactNode } from "react";
import { BackHandler, View } from "react-native";
import {
  BottomSheetModal,
  BottomSheetScrollView,
  BottomSheetBackdrop,
} from "@gorhom/bottom-sheet";
import { ReduceMotion } from "react-native-reanimated";

import Maximize2 from "lucide-react-native/icons/maximize-2";
import { useTranslation } from "react-i18next";
import { useTheme } from "../theme";
import { Txt } from ".";
import { IconButton } from "./IconButton";
export function Sheet({
  open,
  title,
  onClose,
  onExpand,
  children,
  list = false,
  snapPoints = ["55%", "92%"],
  index = 0,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  onExpand?: () => void;
  children: ReactNode;
  list?: boolean;
  snapPoints?: (string | number)[];
  index?: number;
}) {
  const ref = useRef<BottomSheetModal>(null),
    c = useTheme(),
    { t } = useTranslation();
  const presented = useRef(false);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open) {
      if (presented.current) ref.current?.dismiss();
      return;
    }
    presented.current = true;
    ref.current?.present();
    const back = BackHandler.addEventListener("hardwareBackPress", () => {
      ref.current?.dismiss();
      return true;
    });
    return () => back.remove();
  }, [open]);
  return (
    <BottomSheetModal
      ref={ref}
      index={index}
      snapPoints={snapPoints}
      enableDynamicSizing={false}
      enablePanDownToClose
      overrideReduceMotion={ReduceMotion.System}
      onDismiss={() => {
        presented.current = false;
        closeRef.current();
      }}
      backgroundStyle={{ backgroundColor: c.surface, borderTopLeftRadius: dsRadius.lg, borderTopRightRadius: dsRadius.lg }}
                style={dsShadow.sheet[c.dark ? "night" : "parchment"]}
      handleIndicatorStyle={{ backgroundColor: c.ink2 }}
      backdropComponent={(props) => (
        <BottomSheetBackdrop
          {...props}
                    style={[props.style, { backgroundColor: c.scrim }]}
                    opacity={1}
          appearsOnIndex={0}
          disappearsOnIndex={-1}
          pressBehavior="close"
        />
      )}
    >
      <View accessibilityViewIsModal style={{ flex: 1 }}>
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            paddingHorizontal: dsSpace[4],
            borderBottomWidth: 1,
            borderColor: c.hair,
          }}
        >
          <Txt kind="title" style={{ flex: 1 }}>{title}</Txt>
          {onExpand && (
            <IconButton
              accessibilityLabel={t("expand")}
              icon={<Maximize2 size={20} color={c.ink} />}
              onPress={onExpand}
            />
          )}
          <IconButton
            accessibilityLabel={t("close")}
            icon={<X size={22} color={c.ink} />}
            onPress={() => ref.current?.dismiss()}
          />
        </View>
        {list ? (
          <ContentList sheet>{children}</ContentList>
        ) : (
          <BottomSheetScrollView
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ padding: 20, paddingBottom: dsSpace[12], gap: dsSpace[4] }}
          >
            {children}
          </BottomSheetScrollView>
        )}
      </View>
    </BottomSheetModal>
  );
}
