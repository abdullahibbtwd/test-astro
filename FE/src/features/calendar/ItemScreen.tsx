import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useApi } from "../../api/resource";
import { useFlags } from "../../lib/flags";
import { useProfile } from "../shared/useProfile";
import { Generated } from "../shared/Blocks";
import type { CalendarItem } from "../../../contracts/spec-types";
export default function ItemScreen() {
  const { id: item } = useLocalSearchParams<{ id: string }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    flags = useFlags(),
    query = useApi<CalendarItem>(
      `/profiles/${id}/calendar/items/${encodeURIComponent(item)}`,
      "CalendarItem",
      !!id,
    ),
    data = query.data;
  return (
    <Screen back title={data?.label ?? t("calendar")}>
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Txt muted>{[data.start, data.end].filter(Boolean).join(" – ")}</Txt>
          {data.exact_dates?.map((date) => (
            <Txt key={date}>{date}</Txt>
          ))}
          {data.peak && (
            <Txt>
              {t("peak")}: {data.peak}
            </Txt>
          )}
          {data.goal_label && (
            <Txt>
              {data.goal_label} · {t(data.period_kind ?? "periods")}
            </Txt>
          )}
          {data.house_label && <Txt>{data.house_label}</Txt>}
          <Generated
            part={data.text}
            retry={() => {
              void query.retry();
            }}
          >
            {(part) => <Txt kind="reading">{part.text}</Txt>}
          </Generated>
          <Button
            secondary
            label={t("showCalendar")}
            onPress={() =>
              router.push(
                `/calendar?profile=${id}&month=${(data.start ?? data.exact_dates?.[0] ?? data.peak ?? item.match(/\d{4}-\d{2}-\d{2}/)?.[0] ?? new Date().toISOString()).slice(0, 7)}`,
              )
            }
          />
          {flags.askAstrology && (
            <Button
              secondary
              label={t("ask")}
              onPress={() =>
                router.push(
                  `/ask?profile=${id}&item_id=${encodeURIComponent(item)}`,
                )
              }
            />
          )}
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
