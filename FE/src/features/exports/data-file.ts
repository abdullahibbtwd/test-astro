import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";
export async function shareAccountData(data: unknown) {
  if (
    !data ||
    typeof data !== "object" ||
    !("format" in data) ||
    data.format !== "astrology-local-export-v1"
  )
    throw new Error("Invalid account export");
  if (!(await Sharing.isAvailableAsync()))
    throw new Error("File sharing unavailable");
  const file = new File(Paths.cache, `astrology-data-${Date.now()}.json`);
  try {
    file.write(JSON.stringify(data, null, 2));
    await Sharing.shareAsync(file.uri, {
      mimeType: "application/json",
      UTI: "public.json",
    });
  } finally {
    if (file.exists) file.delete();
  }
}
