import { useRef, useState, useCallback, type ReactNode } from "react";
import {
  router,
  useLocalSearchParams,
  usePathname,
  useFocusEffect,
} from "expo-router";
import { useTranslation } from "react-i18next";
import { Screen } from "../../design/components";
import { Sheet } from "../../design/components/Sheet";
export function ReportSurface({
  title,
  children,
}: {
  title?: string;
  children: ReactNode;
  back?: boolean;
}) {
  const params = useLocalSearchParams(),
    path = usePathname(),
    [focused, setFocused] = useState(false),
    { t } = useTranslation();
  const active = useRef(false);
  useFocusEffect(
    useCallback(() => {
      active.current = true;
      setFocused(true);
      return () => {
        active.current = false;
        setFocused(false);
      };
    }, []),
  );
  if (params.full === "1")
    return (
      <Screen back title={title ?? t("reading")}>
        {children}
      </Screen>
    );
  return (
    <Sheet
      open={focused}
      title={title ?? t("reading")}
      snapPoints={["25%", "55%", "92%"]}
      index={1}
      onClose={() => {
        if (active.current) router.back();
      }}
      onExpand={() => {
        active.current = false;
        router.push({
          pathname: "/map/full",
          params: { ...params, full: "1", reportPath: path },
        });
      }}
    >
      {children}
    </Sheet>
  );
}
