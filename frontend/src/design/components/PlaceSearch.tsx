import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { usePlaces } from "../../api/hooks";
import { useApp } from "../../lib/state";
import type { Place } from "../../../contracts/spec-types";
import { Button, Card, ErrorNotice, Field, Row, Skeleton, Txt } from "./index";
export function PlaceSearch({
  onConfirm,
}: {
  onConfirm: (place: Place) => void;
}) {
  const { t } = useTranslation(),
    app = useApp();
  const [text, setText] = useState(""),
    [debounced, setDebounced] = useState(""),
    [selected, setSelected] = useState<Place | null>(null);
  const results = usePlaces(debounced);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(text.trim()), 250);
    return () => clearTimeout(id);
  }, [text]);
  const choose = (place: Place) => {
    app.update({
      recent: [
        place,
        ...app.recent.filter((p) => p.place_id !== place.place_id),
      ].slice(0, 5),
    });
    onConfirm(place);
  };
  return (
    <>
      <Field
        label={t("searchPlace")}
        value={text}
        onChangeText={(value) => {
          setText(value);
          setSelected(null);
        }}
        autoCorrect={false}
      />
      {selected ? (
        <Card>
          <Txt kind="title">{selected.name}</Txt>
          <Txt muted>
            {[selected.admin1, selected.country_name]
              .filter(Boolean)
              .join(" · ")}
          </Txt>
          <Txt>{t("confirmPlace")}</Txt>
          <Button label={t("yes")} onPress={() => choose(selected)} />
          <Button
            secondary
            label={t("change")}
            onPress={() => setSelected(null)}
          />
        </Card>
      ) : (
        <>
          {text.length === 0 && app.recent.length > 0 && (
            <Txt kind="caption" muted>
              {t("recent")}
            </Txt>
          )}
          {results.isFetching && <Skeleton />}
          <ErrorNotice
            error={results.error}
            retry={() => void results.refetch()}
          />
          {(text.length === 0 ? app.recent : (results.data ?? [])).map(
            (place) => (
              <Row
                key={place.place_id}
                label={place.name}
                detail={[place.admin1, place.country_name]
                  .filter(Boolean)
                  .join(" · ")}
                onPress={() => setSelected(place)}
              />
            ),
          )}
          {debounced.length >= 2 &&
            !results.isFetching &&
            results.data?.length === 0 && <Txt muted>{t("noPlaces")}</Txt>}
        </>
      )}
    </>
  );
}
