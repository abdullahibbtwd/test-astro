import { Redirect, useLocalSearchParams } from "expo-router";
export default function Page() {
  const params = useLocalSearchParams<{ profile?: string; month?: string }>();
  return (
    <Redirect
      href={{ pathname: "/(tabs)/ahead", params: { ...params, view: "year" } }}
    />
  );
}
export { RouteError as ErrorBoundary } from "../../src/design/components/RouteError";
