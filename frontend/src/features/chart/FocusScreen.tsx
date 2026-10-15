import { useState } from "react";
import { Screen, Skeleton, ErrorNotice } from "../../design/components";
import { useProfile } from "../shared/useProfile";
import { useChart, useCatalogue } from "../../api/hooks";
import { InteractiveWheel } from "./InteractiveWheel";
import { ChartDetailSheet } from "./ChartDetailSheet";
import type { Selection } from "./facts";
export default function FocusScreen() {
  const { id, profile } = useProfile(),
    chart = useChart(id, profile?.chart_key),
    c = useCatalogue().data,
    [selection, select] = useState<Selection | null>(null);
  return (
    <Screen back title={profile?.label} scrollProps={{ scrollEnabled: false }}>
      {chart.data ? (
        <>
          <InteractiveWheel
            chart={chart.data}
            catalogue={c}
            selection={selection}
            select={select}
          />
          {selection && (
            <ChartDetailSheet
              chart={chart.data}
              catalogue={c}
              selection={selection}
              select={select}
              close={() => select(null)}
            />
          )}
        </>
      ) : (
        <Skeleton />
      )}
      <ErrorNotice error={chart.error} />
    </Screen>
  );
}
