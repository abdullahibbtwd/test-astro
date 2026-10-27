import { type as dsType, space as dsSpace } from "../../design-system/theme/tokens";
import { ChevronDown, Check } from "../../design-system/LegacyIcons";
import { useState } from "react";
import { Pressable, View } from "react-native";


import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import type { BirthProfile } from "../../../contracts/spec-types";
import { useProfiles } from "../../api/hooks";
import { useApp } from "../../lib/state";
import { useTheme } from "../theme";
import { Txt, Row, ErrorNotice } from ".";
import { Sheet } from "./Sheet";
export function ProfilePicker({
  open,
  selectedId,
  disabledId,
  onSelect,
  onClose,
  addPersonParams,
}: {
  open: boolean;
  selectedId?: string | null;
  disabledId?: string;
  onSelect: (id: string) => void;
  onClose: () => void;
  /** When set, Add person returns here after save (e.g. match flow). */
  addPersonParams?: { returnTo: "match"; a?: string };
}) {
  const profiles = useProfiles(),
    app = useApp(),
    { t } = useTranslation(),
    c = useTheme();
  const recent = app.recentProfileIds ?? [];
  const rank = (p: BirthProfile) =>
    p.is_self
      ? -2
      : recent.includes(p.profile_id)
        ? recent.indexOf(p.profile_id)
        : recent.length;
  return (
    <Sheet list open={open} title={t("choosePerson")} onClose={onClose}>
      {[...(profiles.data ?? [])]
        .sort((a, b) => rank(a) - rank(b))
        .map((p) => (
          <Pressable
            key={p.profile_id}
            accessibilityRole="radio"
            accessibilityLabel={p.label}
            accessibilityState={{
              checked: p.profile_id === selectedId,
              disabled: p.profile_id === disabledId,
            }}
            disabled={p.profile_id === disabledId}
            onPress={() => {
              app.update({
                recentProfileIds: [
                  p.profile_id,
                  ...recent.filter((id) => id !== p.profile_id),
                ].slice(0, 20),
              });
              onSelect(p.profile_id);
              onClose();
            }}
            style={{
              minHeight: 64,
              opacity: p.profile_id === disabledId ? 0.4 : 1,
              flexDirection: "row",
              gap: dsSpace[3],
              alignItems: "center",
            }}
          >
            <View style={{ flex: 1 }}>
              <Txt>{p.label}</Txt>
              <Txt kind="caption" muted>
                {t(p.is_self ? "self" : p.relation)}
              </Txt>
            </View>
            {p.profile_id === selectedId && (
              <Check size={22} color={c.accent} />
            )}
          </Pressable>
        ))}
      <Row
        label={t("addPerson")}
        onPress={() => {
          onClose();
          if (addPersonParams?.returnTo === "match") {
            const a = addPersonParams.a ? `&a=${encodeURIComponent(addPersonParams.a)}` : "";
            router.push(`/profile/charts/new?returnTo=match${a}`);
            return;
          }
          router.push("/profile/charts/new");
        }}
      />
      <ErrorNotice
        error={profiles.error}
        retry={() => void profiles.refetch()}
      />
    </Sheet>
  );
}
export function ProfileSwitcher({
  selectedId,
  onSelect,
}: {
  selectedId?: string;
  onSelect?: (id: string) => void;
}) {
  const profiles = useProfiles(),
    app = useApp(),
    c = useTheme(),
    { t } = useTranslation(),
    [open, setOpen] = useState(false);
  const id = selectedId ?? app.activeProfileId ?? app.me?.self_profile_id;
  const person =
    profiles.data?.find((p) => p.profile_id === id) ??
    profiles.data?.find((p) => p.is_self);
  const label = person?.label ?? t("choosePerson");
  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t("showingPerson", { name: label })}
        onPress={() => setOpen(true)}
        style={{
          minHeight: 44,
          flexDirection: "row",
          alignItems: "center",
          gap: dsSpace[2],
        }}
      >
        <View
          style={{
            width: 28,
            height: 28,
            borderRadius: 14,
            backgroundColor: c.accentSoft,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Txt kind="caption">{label.charAt(0)}</Txt>
        </View>
        <Txt
          numberOfLines={1}
          style={{ maxWidth: 160, fontFamily: dsType.input.fontFamily }}
        >
          {label}
        </Txt>
        <ChevronDown size={16} color={c.ink} />
      </Pressable>
      <ProfilePicker
        open={open}
        selectedId={person?.profile_id}
        onClose={() => setOpen(false)}
        onSelect={(value) => {
          app.update({ activeProfileId: value });
          onSelect?.(value);
        }}
      />
    </>
  );
}
