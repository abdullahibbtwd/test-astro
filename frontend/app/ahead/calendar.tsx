import { Redirect, useLocalSearchParams } from "expo-router";
export default function LegacyAhead() {
  const params = useLocalSearchParams();
  return (
    <Redirect
      href={{
        pathname: "/(tabs)/ahead",
        params: { ...params, view: "calendar" },
      }}
    />
  );
}
