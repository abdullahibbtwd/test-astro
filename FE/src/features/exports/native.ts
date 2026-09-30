import { Asset } from "expo-asset";
import { File, Paths } from "expo-file-system";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import * as MediaLibrary from "expo-media-library/legacy";
import { Skia, ImageFormat } from "@shopify/react-native-skia";
import {
  renderChartResolved,
  expandGlyphUses,
} from "../../../packages/wheel-core/resolved";
import { documentShell, slug } from "./document";
import type { ChartData } from "../../../contracts/spec-types";
const assets = {
  inter: require("../../../assets/fonts/Inter-Regular.ttf"),
  bold: require("../../../assets/fonts/Inter-SemiBold.ttf"),
  serif: require("../../../assets/fonts/SourceSerif4-Regular.ttf"),
};
async function localFont(module: number) {
  const a = Asset.fromModule(module);
  await a.downloadAsync();
  return new File(a.localUri ?? a.uri);
}
export async function exportPdf(
  title: string,
  body: string,
  disclaimer: string,
  brand: string,
  filename: string,
) {
  const [inter, bold, serif] = await Promise.all(
    Object.values(assets).map(async (a) => (await localFont(a)).base64()),
  );
  const result = await Print.printToFileAsync({
    html: documentShell(title, body, disclaimer, brand, {
      inter: inter!,
      bold: bold!,
      serif: serif!,
    }),
    width: 595.28,
    height: 841.89,
  });
  const target = new File(Paths.cache, `${slug(filename)}.pdf`);
  if (target.exists) target.delete();
  await new File(result.uri).move(target);
  await Sharing.shareAsync(target.uri, {
    mimeType: "application/pdf",
    UTI: "com.adobe.pdf",
  });
  return target.uri;
}
export async function exportChartImage(
  chart: ChartData,
  caption: string[],
  dark: boolean,
  format: "png" | "jpg",
  filename: string,
  save: boolean,
) {
  const surface = Skia.Surface.MakeOffscreen(2048, 2400);
  if (!surface) throw new Error("Image surface unavailable");
  const canvas = surface.getCanvas(),
    paint = Skia.Paint();
  canvas.clear(Skia.Color(dark ? "#1A2030" : "#FAFAF8"));
  const fontFile = await localFont(assets.inter),
    fontData = Skia.Data.fromBase64(await fontFile.base64()),
    typeface = Skia.Typeface.MakeFreeTypeFaceFromData(fontData),
    font = Skia.Font(typeface ?? undefined, 40);
  const fontManager = Skia.TypefaceFontProvider.Make();
  if (typeface) fontManager.registerFont(typeface, "Inter");
  const source = expandGlyphUses(
    renderChartResolved(chart, dark ? "dark" : "light"),
  );
  const svg = Skia.SVG.MakeFromString(source, fontManager);
  if (!svg) throw new Error("SVG unavailable");
  canvas.drawSvg(svg, 2048, 2048);
  paint.setColor(Skia.Color(dark ? "#E7E9EE" : "#232A38"));
  caption.forEach((line, i) => {
    let size = 40;
    font.setSize(size);
    while (font.measureText(line).width > 1900 && size > 20)
      font.setSize(--size);
    canvas.drawText(
      line,
      (2048 - font.measureText(line).width) / 2,
      2110 + i * 68,
      paint,
      font,
    );
  });
  surface.flush();
  const image = surface.makeImageSnapshot(),
    file = new File(Paths.cache, `${slug(filename)}.${format}`);
  file.write(
    image.encodeToBase64(
      format === "png" ? ImageFormat.PNG : ImageFormat.JPEG,
      95,
    ),
    { encoding: "base64" },
  );
  if (save) {
    const permission = await MediaLibrary.requestPermissionsAsync(true);
    if (!permission.granted) throw new Error("Photo permission required");
    await MediaLibrary.saveToLibraryAsync(file.uri);
  } else
    await Sharing.shareAsync(file.uri, {
      mimeType: format === "png" ? "image/png" : "image/jpeg",
    });
  return file.uri;
}
