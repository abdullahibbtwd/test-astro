import { Keyboard, SectionList, TextInput, View } from "react-native";
import Search from "lucide-react-native/icons/search";
import X from "lucide-react-native/icons/x";
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
          borderRadius: 28,
          backgroundColor: c.surface,
          paddingLeft: 16,
          paddingRight: 4,
          gap: 8,
          borderWidth: 1,
          borderColor: c.hair,
        }}
      >
        <Search size={20} color={c.ink2} />
        <TextInput
          accessibilityLabel={t("searchMap")}
          placeholder={t("searchMap")}
          placeholderTextColor={c.ink3}
          value={input}
          onChangeText={setInput}
          style={{
            flex: 1,
            minHeight: 44,
            color: c.ink,
            fontFamily: "Inter",
            fontSize: 16,
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
            marginTop: 4,
            height: 320,
            backgroundColor: c.surface,
            borderRadius: 16,
            elevation: 8,
          }}
          contentContainerStyle={{ padding: 16 }}
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
