import catalogueTr from "../../i18n/catalogue-fallback.tr.json";
import catalogueEn from "../../i18n/catalogue-fallback.en.json";
import { useMutation, useQuery } from "@tanstack/react-query";
import * as Notifications from "expo-notifications";
import { request, setSession, refreshToken, updateSessionMe } from "../client";
import { queryClient, keys } from "../query";
import { useApp, resetLocalState } from "../../lib/state";
import { privateStorage } from "../../lib/storage";
import type {
  BirthProfile,
  ChartData,
  BirthProfileInput,
  Me,
  Place,
  PlaceCandidate,
  Session,
  Config,
  Catalogue,
  ReportPage,
} from "../../../contracts/spec-types";
function useResource<T>(
  name: string,
  path: string,
  schema: string,
  enabled = true,
) {
  const lang = useApp((s) => s.language);
  return useQuery({
    queryKey: keys.resource(name, lang, path),
    queryFn: () => request<T>("GET", path, schema),
    enabled,
  });
}
export const useMe = () =>
  useResource<Me>(
    "me",
    "/me",
    "Me",
    useApp((s) => s.signedIn),
  );
export const useProfiles = () =>
  useResource<BirthProfile[]>(
    "profiles",
    "/profiles",
    "BirthProfile[]",
    useApp((s) => s.signedIn),
  );
export const useConfig = () =>
  useResource<Config>("config", "/meta/config", "Config");
export function useCatalogue() {
  const lang = useApp((s) => s.language),
    signedIn = useApp((s) => s.signedIn);
  return useQuery({
    queryKey: keys.resource("catalogue", lang),
    queryFn: () => request<Catalogue>("GET", "/meta/catalogue", "Catalogue"),
    initialData: (lang === "tr" ? catalogueTr : catalogueEn) as Catalogue,
    initialDataUpdatedAt: 0,
    enabled: signedIn,
  });
}
export const usePlaces = (text: string) =>
  useResource<PlaceCandidate[]>(
    "places",
    `/places/search?q=${encodeURIComponent(text)}&kind=birth`,
    "PlaceCandidate[]",
    text.trim().length >= 2,
  );
export function useActions() {
  const mutate = useMutation({
    mutationFn: async ({
      method,
      path,
      body,
      schema,
    }: {
      method: "POST" | "PATCH" | "DELETE";
      path: string;
      body?: unknown;
      schema?: string;
    }) => request<any>(method, path, schema, body),
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
  });
  return {
    ...mutate,
    startEmail: (email: string) =>
      mutate.mutateAsync({
        method: "POST",
        path: "/auth/email/start",
        body: { email, lang: useApp.getState().language },
      }),
    verify: async (email: string, code: string) => {
      const data = (await mutate.mutateAsync({
        method: "POST",
        path: "/auth/email/verify",
        schema: "Session",
        body: { email, code },
      })) as Session;
      queryClient.clear();
      if (!data.me.self_profile_id)
        useApp.getState().editDraft({ step: "consent", profileId: undefined });
      await setSession(data);
      if (data.me.language !== useApp.getState().language)
        await request("PATCH", "/me", "Me", {
          language: useApp.getState().language,
        });
      return data;
    },
    patchMe: async (body: unknown) => {
      const me = (await mutate.mutateAsync({
        method: "PATCH",
        path: "/me",
        schema: "Me",
        body,
      })) as Me;
      await updateSessionMe(me);
      return me;
    },
    saveProfile: async (body: Partial<BirthProfileInput>, id?: string) => {
      const profile = (await mutate.mutateAsync({
        method: id ? "PATCH" : "POST",
        path: id ? `/profiles/${id}` : "/profiles",
        schema: "BirthProfile",
        body,
      })) as BirthProfile;
      if (profile.is_self) {
        useApp.getState().editDraft({ profileId: profile.profile_id });
        const me = useApp.getState().me;
        if (me)
          await updateSessionMe({ ...me, self_profile_id: profile.profile_id });
      }
      await queryClient.invalidateQueries();
      return profile;
    },
    removeProfile: (id: string) =>
      mutate.mutateAsync({ method: "DELETE", path: `/profiles/${id}` }),
    reverse: (lat: number, lon: number) =>
      request<Place | null>("GET", `/places/reverse?lat=${lat}&lon=${lon}`),
    logout: async () => {
      try {
        await request("POST", "/auth/logout", undefined, {
          refresh_token: refreshToken(),
        });
      } finally {
        await clearSession();
      }
    },
    deleteAccount: async () => {
      await mutate.mutateAsync({ method: "DELETE", path: "/me" });
      await clearSession();
    },
    exportData: () =>
      mutate.mutateAsync({ method: "POST", path: "/me/export" }),
  };
}
async function clearSession() {
  await queryClient.cancelQueries();
  queryClient.clear();
  await Notifications.cancelAllScheduledNotificationsAsync();
  await setSession(null);
  privateStorage.clear();
  resetLocalState();
}

export const useReports = (type: string) =>
  useResource<ReportPage>(
    "reports",
    `/reports${type ? "?type=" + type : ""}`,
    "ReportPage",
  );

export function useChart(id: string, chartKey?: string) {
  const lang = useApp((s) => s.language);
  return useQuery({
    queryKey: keys.resource("chart", lang, id, chartKey),
    queryFn: () =>
      request<ChartData>("GET", `/profiles/${id}/chart`, "ChartData"),
    staleTime: Infinity,
    enabled: !!id,
  });
}
