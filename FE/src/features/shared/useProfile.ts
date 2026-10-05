import { useEffect } from "react";
import { useLocalSearchParams } from "expo-router";
import { useProfiles } from "../../api/hooks";
import { useApp } from "../../lib/state";
export function useProfile(tab = false) {
  const { profile: id } = useLocalSearchParams<{ profile?: string }>(),
    app = useApp(),
    query = useProfiles();
  const update = app.update;
  useEffect(() => {
    if (tab && id) update({ activeProfileId: id });
  }, [tab, id, update]);
  const profile = query.data?.find(
    (p) =>
      p.profile_id ===
      (tab
        ? (app.activeProfileId ?? id ?? app.me?.self_profile_id)
        : (id ?? app.activeProfileId ?? app.me?.self_profile_id)),
  );
  return {
    profile,
    query,
    id: profile?.profile_id ?? "",
    tz: profile?.is_self
      ? (app.me?.current_place?.tz ?? profile.birth.tz)
      : (profile?.current_place?.tz ?? profile?.birth.tz ?? "Europe/Istanbul"),
  };
}
