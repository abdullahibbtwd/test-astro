import { useState } from "react";
import { Platform } from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { useTranslation } from "react-i18next";
import { Button, Row } from "./index";
import { formatDate } from "../../lib/dates";
import { useApp } from "../../lib/state";
export function DateTimeField({
  mode,
  value,
  onChange,
}: {
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
      <Row
        label={t(mode === "date" ? "birthDate" : "birthTime")}
        detail={
          value
            ? mode === "date"
              ? formatDate(value, lang)
              : value
            : t(mode === "date" ? "selectDate" : "selectTime")
        }
        onPress={() => setOpen(true)}
      />
      {open && (
        <>
          <DateTimePicker
            value={date}
            mode={mode}
            is24Hour
            locale={lang}
            display={Platform.OS === "ios" ? "spinner" : "default"}
            minimumDate={mode === "date" ? new Date(1900, 0, 1) : undefined}
            maximumDate={mode === "date" ? new Date() : undefined}
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
