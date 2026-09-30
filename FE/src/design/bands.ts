export function bandColor(band: string, dark = false) {
  if (["strongly_supportive", "excellent"].includes(band))
    return dark ? "#7CC4AD" : "#2F6B5A";
  if (["supportive", "favorable", "good"].includes(band))
    return dark ? "#5FAF97" : "#4F9A84";
  if (band === "mixed") return dark ? "#E0A94E" : "#A8761E";
  if (["challenging", "strongly_challenging", "avoid"].includes(band))
    return dark ? "#E07A60" : "#C0583F";
  return dark ? "#8A91A0" : "#6B7180";
}
