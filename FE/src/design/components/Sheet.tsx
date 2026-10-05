import { useEffect, useRef, type ReactNode } from "react";
import { BackHandler, View } from "react-native";
import { BottomSheetModal, BottomSheetScrollView, BottomSheetBackdrop } from "@gorhom/bottom-sheet";
import { ReduceMotion } from "react-native-reanimated";
import { X, Maximize2 } from "lucide-react-native";
import { useTranslation } from "react-i18next";
import { useTheme } from "../theme";
import { Txt } from ".";
import { IconButton } from "./IconButton";
export function Sheet({ open, title, onClose, onExpand, children, snapPoints = ["55%", "92%"], index = 0 }: { open: boolean; title: string; onClose: () => void; onExpand?: () => void; children: ReactNode; snapPoints?: (string | number)[]; index?: number }) {
  const ref = useRef<BottomSheetModal>(null), c = useTheme(), { t } = useTranslation();
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useEffect(() => {
    if (!open) { ref.current?.dismiss(); return; }
    ref.current?.present();
    const back = BackHandler.addEventListener("hardwareBackPress", () => { ref.current?.dismiss(); return true; });
    return () => back.remove();
  }, [open]);
  return <BottomSheetModal ref={ref} index={index} snapPoints={snapPoints} enableDynamicSizing={false} enablePanDownToClose overrideReduceMotion={ReduceMotion.System} onDismiss={() => closeRef.current()} backgroundStyle={{ backgroundColor: c.surface }} handleIndicatorStyle={{ backgroundColor: c.ink2 }} backdropComponent={props => <BottomSheetBackdrop {...props} appearsOnIndex={0} disappearsOnIndex={-1} pressBehavior="close" />}>
    <View accessibilityViewIsModal style={{ flex: 1 }}>
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 16, borderBottomWidth: 1, borderColor: c.hair }}>
        <Txt style={{ flex: 1, fontFamily: "Inter-SemiBold" }}>{title}</Txt>
        {onExpand && <IconButton accessibilityLabel={t("expand")} icon={<Maximize2 size={20} color={c.ink} />} onPress={onExpand} />}
        <IconButton accessibilityLabel={t("close")} icon={<X size={22} color={c.ink} />} onPress={() => ref.current?.dismiss()} />
      </View>
      <BottomSheetScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingBottom: 48, gap: 16 }}>{children}</BottomSheetScrollView>
    </View>
  </BottomSheetModal>;
}
