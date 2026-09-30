import { Redirect } from "expo-router";
import { useApp } from "../src/lib/state";
export default function Index() {
  const app = useApp();
  if (!app.signedIn) return <Redirect href="/(auth)/welcome" />;
  if (
    !app.me?.self_profile_id ||
    (app.draft.profileId && app.draft.step !== "complete")
  )
    return <Redirect href={`/(onboarding)/${app.draft.step}`} />;
  return <Redirect href="/(tabs)" />;
}
