import { Fragment, useMemo, useState } from "react";
import { useWindowDimensions } from "react-native";
import { SvgCss } from "react-native-svg/css";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Choices,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { PlaceSearch } from "../../design/components/PlaceSearch";
import { useApi } from "../../api/resource";
import { useProfile } from "../shared/useProfile";
import { useApp } from "../../lib/state";
import { useTheme } from "../../design/theme";
import { Generated } from "../shared/Blocks";
import { nativeWheelSvg } from "../../../packages/wheel-core/native-svg";
import type { SolarReturn } from "../../../contracts/spec-types";
export default function SolarReturnScreen() {
  const params = useLocalSearchParams<{ year: string }>(),
    { id, profile, tz } = useProfile(),
    app = useApp(),
    { t } = useTranslation(),
    c = useTheme(),
    { width } = useWindowDimensions(),
    [place, setPlace] = useState<string>(),
    [selectPlace, setSelectPlace] = useState(false);
  const current =
    place ??
    (profile?.is_self
      ? app.me?.current_place?.place_id
      : profile?.current_place?.place_id) ??
    profile?.birth.place.place_id;
  const query = useApi<SolarReturn>(
      `/profiles/${id}/solar-return?year=${params.year}${current ? `&place_id=${encodeURIComponent(current)}` : ""}`,
      "SolarReturn",
      !!id,
    ),
    data = query.data;
  const xml = useMemo(
    () =>
      data
        ? nativeWheelSvg(data.chart, c.bg === "#1A2030" ? "dark" : "light")
        : null,
    [data, c.bg],
  );
  return (
    <Screen back title={`${t("solar_return")} ${params.year}`}>
      <Choices>
        {[new Date().getFullYear(), new Date().getFullYear() + 1].map(
          (year) => (
            <Button
              key={year}
              secondary
              label={String(year)}
              onPress={() => router.setParams({ year: String(year) })}
            />
          ),
        )}
      </Choices>
      <Txt>{t("birthdayPlace")}</Txt>
      <Button
        secondary
        label={data?.place.name ?? t("changePlace")}
        onPress={() => setSelectPlace(!selectPlace)}
      />
      {selectPlace && (
        <PlaceSearch
          onConfirm={(value) => {
            setPlace(value.place_id);
            setSelectPlace(false);
          }}
        />
      )}
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Txt>
            {new Intl.DateTimeFormat(app.language, {
              dateStyle: "long",
              timeStyle: "short",
              timeZone: tz,
            }).format(new Date(data.return_utc))}
          </Txt>
          {xml && (
            <SvgCss xml={xml} width="100%" height={Math.min(width - 40, 480)} />
          )}
          <Generated
            part={data.reading}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => (
              <>
                {part.sections.map((section) => (
                  <Fragment key={section.key}>
                    <Txt key={`${section.key}title`} kind="title">
                      {section.title}
                    </Txt>
                    <Txt key={section.key} kind="reading">
                      {section.text}
                    </Txt>
                  </Fragment>
                ))}
              </>
            )}
          </Generated>
        </>
      )}
      <ErrorNotice
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    </Screen>
  );
}
