import { create } from "zustand";
import { getLocales } from "expo-localization";
import { privateStorage } from "./storage";
import type { Lang, Me, Place } from "../../contracts/spec-types";
export type Draft = {
  step: string;
  name: string;
  date: string;
  time: string;
  place: Place | null;
  consent: boolean;
  marketing: boolean;
  profileId?: string;
};
const emptyDraft: Draft = {
  step: "consent",
  name: "",
  date: "",
  time: "",
  place: null,
  consent: false,
  marketing: false,
};
type State = {
  ready: boolean;
  signedIn: boolean;
  language: Lang;
  languageChosen: boolean;
  theme: Me["theme"];
  activeProfileId: string | null;
  me: Me | null;
  draft: Draft;
  recent: Place[];
  recentProfileIds: string[];
  update: (
    values: Partial<Omit<State, "update" | "editDraft" | "hydrate">>,
  ) => void;
  editDraft: (values: Partial<Draft>) => void;
  hydrate: () => void;
};
export const useApp = create<State>((set, get) => ({
  ready: false,
  signedIn: false,
  language: getLocales()[0]?.languageCode === "tr" ? "tr" : "en",
  languageChosen: false,
  theme: "system",
  activeProfileId: null,
  me: null,
  draft: emptyDraft,
  recent: [],
  recentProfileIds: [],
  update: (values) => {
    set(values);
    const {
      language,
      languageChosen,
      theme,
      activeProfileId,
      draft,
      recent,
      recentProfileIds,
    } = get();
    privateStorage.setItem(
      "preferences",
      JSON.stringify({
        language,
        languageChosen,
        theme,
        activeProfileId,
        draft,
        recent,
        recentProfileIds,
      }),
    );
  },
  editDraft: (values) => get().update({ draft: { ...get().draft, ...values } }),
  hydrate: () => {
    const raw = privateStorage.getItem("preferences");
    if (raw) {
      try {
        set(JSON.parse(raw));
      } catch {
        privateStorage.removeItem("preferences");
      }
    }
    set({ ready: true });
  },
}));
export function resetLocalState() {
  useApp.setState({
    signedIn: false,
    me: null,
    activeProfileId: null,
    draft: { ...emptyDraft },
    recent: [],
    recentProfileIds: [],
  });
}
