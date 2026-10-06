import { View } from "react-native";
import { Txt } from ".";
import { useApp } from "../../lib/state";
import { countryName, countryFlag } from "../../lib/countries";
export function CountryLabel({
  code,
  name,
}: {
  code?: string | null;
  name?: string;
}) {
  const lang = useApp((s) => s.language);
  return (
    <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
      <View accessible={false} importantForAccessibility="no-hide-descendants">
        <Txt>{countryFlag(code ?? "")}</Txt>
      </View>
      <Txt muted>{countryName(code, lang, name)}</Txt>
    </View>
  );
}
