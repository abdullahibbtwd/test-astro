import { Field, SelectField } from "../../design-system/components/Fields";
import { useState } from "react";
import { Platform } from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";
import { Button } from "./index";
import { formatDate } from "../../lib/dates";
import { useApp } from "../../lib/state";
export function DateTimeField({
  mode,
  value,
  onChange,
  label,
  placeholder,
  compact = false,
  minimumDate = new Date(1900, 0, 1),
  maximumDate = new Date(),
}: {
  label?: string;
  placeholder?: string;
  compact?: boolean;
  minimumDate?: Date;
  maximumDate?: Date;
  mode: "date" | "time";
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false),
    { t } = useTranslation(),
    lang = useApp((s) => s.language);
  const date =
    mode === "date"
      ? new Date(`${value || "1990-01-01"}T12:00:00`)
      : new Date(`2000-01-01T${value || "12:00"}:00`);
  return (
    <>
      <Field label={label ?? t(mode === "date" ? "birthDate" : "birthTime")}>
        <SelectField
          accessibilityLabel={
            label ?? t(mode === "date" ? "birthDate" : "birthTime")
          }
          valueLabel={
            value
              ? mode === "date"
                ? compact
                  ? new Intl.DateTimeFormat(lang === "tr" ? "tr-TR" : "en-GB", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                    }).format(date)
                  : formatDate(value, lang)
                : value
              : (placeholder ??
                t(mode === "date" ? "selectDate" : "selectTime"))
          }
          onPress={() => setOpen(true)}
        />
      </Field>
      {open && (
        <>
          <DateTimePicker
            value={date}
            mode={mode}
            is24Hour
            locale={lang}
            display={Platform.OS === "ios" ? "spinner" : "default"}
            minimumDate={mode === "date" ? minimumDate : undefined}
            maximumDate={mode === "date" ? maximumDate : undefined}
            onChange={(event, selected) => {
              if (Platform.OS === "android") setOpen(false);
              if (event.type === "set" && selected) {
                const pad = (n: number) => String(n).padStart(2, "0");
                onChange(
                  mode === "date"
                    ? `${selected.getFullYear()}-${pad(selected.getMonth() + 1)}-${pad(selected.getDate())}`
                    : `${pad(selected.getHours())}:${pad(selected.getMinutes())}`,
                );
              }
            }}
          />
          {Platform.OS === "ios" && (
            <Button label={t("done")} onPress={() => setOpen(false)} />
          )}
        </>
      )}
    </>
  );
}
