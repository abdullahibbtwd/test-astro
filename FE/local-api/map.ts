import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { mapAcgLines } from "../mock-api/scripts/geo";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
import type {
  BirthProfile,
  AcgLines,
  LinePlaces,
  Lang,
  Body,
  Angle,
} from "../contracts/spec-types";
export class LiveMap {
  constructor(private store: Store) {}
  private async data(profile: BirthProfile) {
    const key = "map:v1:" + profile.chart_key;
    const cached = this.store.get(key);
    if (cached) return cached;
    const raw = this.store.get("raw:" + profile.profile_id);
    if (!raw)
      throw Object.assign(new Error("Chart unavailable"), { statusCode: 503 });
    const result = await runReadingBridge("map_bridge.py", { chart: raw });
    const lines = validate<AcgLines>(
      "AcgLines",
      mapAcgLines(profile.chart_key, result.lines, result.parans),
    );
    const value = { lines, by_line: result.by_line };
    this.store.put(key, value);
    return value;
  }
  async lines(profile: BirthProfile): Promise<AcgLines> {
    return (await this.data(profile)).lines;
  }
  async places(
    profile: BirthProfile,
    body: string,
    angle: string,
    lang: Lang,
    limit: number,
  ): Promise<LinePlaces> {
    const cat = fixture(`catalogue.${lang}`);
    if (
      !Object.hasOwn(cat.bodies, body) ||
      !Object.hasOwn(cat.angles, angle) ||
      !Number.isInteger(limit) ||
      limit < 1 ||
      limit > 50
    )
      throw Object.assign(new Error("Invalid line"), { statusCode: 400 });
    const data = await this.data(profile);
    return validate<LinePlaces>("LinePlaces", {
      line: {
        body: body as Body,
        angle: angle as Angle,
        planet_label: cat.bodies[body],
        angle_label: cat.angles[angle].line,
      },
      places: (data.by_line[`${body}|${angle}`] ?? [])
        .slice(0, limit)
        .map((p: any) => ({
          place_id: p.place_id,
          name: lang === "tr" ? p.name_tr : p.name,
          country_code: p.country_code,
          distance_km_rounded: p.distance_km_rounded,
          tier: p.tier,
          tier_label: cat.tiers[p.tier],
        })),
    });
  }
}
