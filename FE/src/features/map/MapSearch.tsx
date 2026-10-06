import { type as dsType, space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { Search, X } from "../../design-system/LegacyIcons";
import { Keyboard, SectionList, TextInput, View } from "react-native";


import { IconButton } from "../../design/components/IconButton";
import { useTheme } from "../../design/theme";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Txt, Row, ErrorNotice, Skeleton } from "../../design/components";
import { useApi } from "../../api/resource";
import type { PlaceCandidate } from "../../../contracts/spec-types";
export function MapSearch({
  onSelect,
  areasOnly = false,
}: {
  onSelect: (place: PlaceCandidate) => void;
  areasOnly?: boolean;
}) {
  const c = useTheme();
  const { t } = useTranslation(),
    [input, setInput] = useState(""),
    [search, setSearch] = useState("");
  useEffect(() => {
    const timeout = setTimeout(() => setSearch(input.trim()), 300);
    return () => clearTimeout(timeout);
  }, [input]);
  const cities = useApi<PlaceCandidate[]>(
    `/places/search?kind=city&q=${encodeURIComponent(search)}`,
    "PlaceCandidate[]",
    search.length >= 2 && !areasOnly,
  );
  const areas = useApi<PlaceCandidate[]>(
    `/places/search?kind=area&q=${encodeURIComponent(search)}`,
    "PlaceCandidate[]",
    search.length >= 2,
  );
  return (
    <View style={{ zIndex: 20 }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          minHeight: 48,
          borderRadius: dsRadius.md,
          backgroundColor: c.surface,
          paddingLeft: dsSpace[4],
          paddingRight: dsSpace[1],
          gap: dsSpace[2],
          borderWidth: 1,
          borderColor: c.borderControl,
        }}
      >
        <Search size={20} color={c.ink2} />
        <TextInput
          accessibilityLabel={t("searchMap")}
          placeholder={t("searchMap")}
          placeholderTextColor={c.ink3}
          selectionColor={c.accent}
          cursorColor={c.accent}
          value={input}
          onChangeText={setInput}
          style={{
            flex: 1,
            minHeight: 44,
            color: c.ink,
            fontFamily: dsType.input.fontFamily,
            fontSize: dsType.input.fontSize,
          }}
        />
        {!!input && (
          <IconButton
            accessibilityLabel={t("clear")}
            icon={<X size={20} color={c.ink} />}
            onPress={() => {
              setInput("");
              setSearch("");
            }}
          />
        )}
      </View>
      {search.length >= 2 && (
        <SectionList<PlaceCandidate>
          keyboardShouldPersistTaps="handled"
          style={{
            marginTop: dsSpace[1],
            height: 320,
            backgroundColor: c.surface,
            borderRadius: dsRadius.md,
            elevation: 8,
          }}
          contentContainerStyle={{ padding: dsSpace[4] }}
          sections={[
            ...(!areasOnly
              ? [
                  {
                    title: t("cities"),
                    data: cities.data ?? [],
                    loading: cities.isFetching,
                    error: cities.error,
                  },
                ]
              : []),
            {
              title: t("areas"),
              data: areas.data ?? [],
              loading: areas.isFetching,
              error: areas.error,
            },
          ]}
          keyExtractor={(p) => p.place_id}
          renderSectionHeader={({ section }) => (
            <>
              <Txt kind="title">{section.title}</Txt>
              {section.loading && <Skeleton variant="lines" lines={2} />}
              <ErrorNotice error={section.error} />
              {!section.loading && !section.data.length && (
                <Txt muted>{t("noResults")}</Txt>
              )}
            </>
          )}
          renderItem={({ item: p }) => (
            <Row
              label={p.name}
              detail={[p.admin1, p.country_name].filter(Boolean).join(" · ")}
              onPress={() => {
                setInput("");
                setSearch("");
                Keyboard.dismiss();
                onSelect(p);
              }}
            />
          )}
        />
      )}
    </View>
  );
}
