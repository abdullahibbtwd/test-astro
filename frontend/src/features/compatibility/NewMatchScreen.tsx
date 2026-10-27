import { Field as DesignField, SelectField } from "../../design-system/components/Fields";
import ArrowUpDown from "lucide-react-native/icons/arrow-up-down";
import { ProfilePicker } from "../../design/components/ProfileSwitcher";
import { IconButton } from "../../design/components/IconButton";
import { useTheme } from "../../design/theme";
import { useParentJobs } from "../../api/use-parent-jobs";
import { useCallback, useEffect, useRef, useState } from "react";
import * as Crypto from "expo-crypto";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Choices,
  Chip,
  Button,
  ErrorNotice,
} from "../../design/components";
import { useProfiles, useCatalogue } from "../../api/hooks";
import { request } from "../../api/client";
import { useApp } from "../../lib/state";
import { useFlags } from "../../lib/flags";
import type {
  Compatibility,
  CompatType,
  FamilyRelation,
} from "../../../contracts/spec-types";
export default function NewMatchScreen() {
  const [picker, setPicker] = useState<"a" | "b" | null>(null),
    c = useTheme();
  const params = useLocalSearchParams<{ other?: string; a?: string }>(),
    { t } = useTranslation(),
    app = useApp(),
    profiles = useProfiles(),
    cat = useCatalogue(),
    flags = useFlags(),
    [a, setA] = useState(params.a ?? app.me?.self_profile_id ?? ""),
    [b, setB] = useState(params.other ?? ""),
    [type, setType] = useState<CompatType>(),
    [family, setFamily] = useState<FamilyRelation>("other"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    key = useRef({ body: "", value: "" });
  const selectB = useCallback(
    (id: string) => {
      setB(id);
      const relation = profiles.data?.find(
        (p) => p.profile_id === id,
      )?.relation;
      if (relation === "partner") setType("love");
      else if (relation === "colleague" || relation === "business_partner")
        setType("work");
      else if (
        ["child", "parent", "family"].includes(relation ?? "") &&
        flags.familyCompatibility
      ) {
        setType("family");
        setFamily(relation === "family" ? "other" : "parent_child");
      } else setType(undefined);
    },
    [profiles.data, flags.familyCompatibility],
  );
  useEffect(() => {
    if (params.other && profiles.data) selectB(params.other);
  }, [params.other, profiles.data, selectB]);
  const create = async () => {
    if (!type || a === b || !a || !b) return;
    setBusy(true);
    setError(undefined);
    try {
      const body = {
          profile_a_id: a,
          profile_b_id: b,
          type,
          ...(type === "family" ? { family_relation: family } : {}),
        },
        signature = JSON.stringify(body);
      if (key.current.body !== signature)
        key.current = { body: signature, value: Crypto.randomUUID() };
      const data = await request<Compatibility>(
        "POST",
        "/compatibility",
        "Compatibility",
        body,
        true,
        key.current.value,
      );
      router.replace(`/match/${data.compatibility_id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  useParentJobs(
    undefined,
    error,
    JSON.stringify([a, b, type, family]),
    !!a && !!b && !!type && !busy,
    create,
  );
  return (
    <Screen back title={t("newCompatibility")}>
      <DesignField label={t("personA")}><SelectField
        accessibilityLabel={t("personA")}
        valueLabel={profiles.data?.find((p) => p.profile_id === a)?.label}
        placeholder={t("choosePerson")}
        onPress={() => setPicker("a")}
      /></DesignField>
      <IconButton
        accessibilityLabel={t("swapPeople")}
        icon={<ArrowUpDown size={22} color={c.ink} />}
        onPress={() => {
          setA(b);
          setB(a);
        }}
      />
      <DesignField label={t("personB")}><SelectField
        accessibilityLabel={t("personB")}
        valueLabel={profiles.data?.find((p) => p.profile_id === b)?.label}
        placeholder={t("choosePerson")}
        onPress={() => setPicker("b")}
      /></DesignField>
      <ProfilePicker
        open={!!picker}
        selectedId={picker === "a" ? a : b}
        disabledId={picker === "a" ? b : a}
        onSelect={(value) => (picker === "a" ? setA(value) : selectB(value))}
        onClose={() => setPicker(null)}
        addPersonParams={{
          returnTo: "match",
          // Keep the other selected person as A after save; new person becomes B.
          a: picker === "a" ? b || app.me?.self_profile_id : a,
        }}
      />
      <Choices>
        {(["love", "family", "work"] as const)
          .filter((value) => value !== "family" || flags.familyCompatibility)
          .map((value) => (
            <Chip
              key={value}
              label={cat.data.compat_types[value]}
              selected={type === value}
              onPress={() => setType(value)}
            />
          ))}
      </Choices>
      {type === "family" && (
        <Choices>
          {(["parent_child", "siblings", "other"] as const).map((value) => (
            <Chip
              key={value}
              label={cat.data.family_relations[value]}
              selected={family === value}
              onPress={() => setFamily(value)}
            />
          ))}
        </Choices>
      )}
      {a && a === b && <Txt>{t("differentPeople")}</Txt>}
      <Button
        label={t("createReport")}
        loading={busy}
        disabled={!a || !b || a === b || !type}
        onPress={() => {
          void create();
        }}
      />
      <ErrorNotice error={error ?? profiles.error} />
    </Screen>
  );
}
