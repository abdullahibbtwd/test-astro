import { useLocalSearchParams } from "expo-router";
import AreaScreen from "../../src/features/map/AreaScreen";
import LineScreen from "../../src/features/map/LineScreen";
import PlaceScreen from "../../src/features/map/PlaceScreen";
export default function FullMapReport() {
  const { reportPath } = useLocalSearchParams<{ reportPath?: string }>();
  return reportPath?.includes("/area/") ? (
    <AreaScreen />
  ) : reportPath?.includes("/line/") ? (
    <LineScreen />
  ) : (
    <PlaceScreen />
  );
}
export { RouteError as ErrorBoundary } from "../../src/design/components/RouteError";
