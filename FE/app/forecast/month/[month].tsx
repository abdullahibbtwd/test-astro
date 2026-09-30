import { useLocalSearchParams } from "expo-router";
import { Screen } from "../../../src/design/components";
import { MonthView } from "../../../src/features/forecast/ForecastViews";
import { useProfile } from "../../../src/features/shared/useProfile";
export default function Page() {
  const { month } = useLocalSearchParams<{ month: string }>(),
    { id } = useProfile();
  return (
    <Screen back title={month}>
      {id && <MonthView profile={id} month={month} lens="general" />}
    </Screen>
  );
}
export { RouteError as ErrorBoundary } from "../../../src/design/components/RouteError";
