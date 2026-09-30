import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Field,
  Txt,
  Row,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useApi } from "../../api/resource";
import type { PlaceCandidate } from "../../../contracts/spec-types";
export function MapSearch({
  onSelect,
  areasOnly = false,
}: {
  onSelect: (place: PlaceCandidate) => void;
  areasOnly?: boolean;
}) {
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
    <>
      <Field label={t("searchMap")} value={input} onChangeText={setInput} />
      {search.length >= 2 && (
        <>
          {[
            ...(!areasOnly ? [{ query: cities, label: "cities" }] : []),
            { query: areas, label: "areas" },
          ].map(({ query, label }) => (
            <ViewResults
              key={label}
              title={t(label)}
              data={query.data}
              loading={query.isFetching}
              error={query.error}
              onSelect={(p) => {
                setInput("");
                setSearch("");
                onSelect(p);
              }}
            />
          ))}
        </>
      )}
    </>
  );
}
function ViewResults({
  title,
  data,
  loading,
  error,
  onSelect,
}: {
  title: string;
  data?: PlaceCandidate[];
  loading: boolean;
  error: unknown;
  onSelect: (p: PlaceCandidate) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <Txt kind="title">{title}</Txt>
      {loading && <Skeleton />}
      <ErrorNotice error={error} />
      {data?.map((p) => (
        <Row
          key={p.place_id}
          label={p.name}
          detail={[p.admin1, p.country_name].filter(Boolean).join(" · ")}
          onPress={() => onSelect(p)}
        />
      ))}
      {data?.length === 0 && <Txt muted>{t("noResults")}</Txt>}
    </>
  );
}
