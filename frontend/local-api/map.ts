import { createHash } from "node:crypto";
import { fileURLToPath, URL } from "node:url";
import { mapRecommendation } from "../mock-api/scripts/recommend";
import { Store } from "./store";
import { runReadingBridge } from "./readings";
import { mapAcgLines } from "../mock-api/scripts/geo";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";
import type {
  BirthProfile,
  AcgLines,
  AcgHeat,
  PlaceReport,
  AreaReport,
  Recommendation,
  RecommendationRequest,
  LinePlaces,
  Lang,
  Body,
  Angle,
} from "../contracts/spec-types";
export class LiveMap {
  constructor(private store: Store) {}
  private async data(profile: BirthProfile) {
    const key = "map:v1:" + profile.chart_key;
    const cached = await this.store.get(key);
    if (cached) return cached;
    const raw = await this.store.get("raw:" + profile.profile_id);
    if (!raw)
      throw Object.assign(new Error("Chart unavailable"), { statusCode: 503 });
    const result = await runReadingBridge("map_bridge.py", { chart: raw });
    const lines = validate<AcgLines>(
      "AcgLines",
      mapAcgLines(profile.chart_key, result.lines, result.parans),
    );
    const value = { lines, by_line: result.by_line };
    await this.store.put(key, value);
    return value;
  }
  async recommend(
    profile: BirthProfile,
    request: RecommendationRequest,
    lang: Lang,
  ): Promise<Recommendation> {
    const cat = fixture(`catalogue.${lang}`);
    const id = createHash("sha256")
      .update(JSON.stringify([profile.chart_key, request]))
      .digest("hex");
    if (!request.goal)
      return validate<Recommendation>("Recommendation", {
        recommendation_id: id,
        status: "needs_goal",
        goal: null,
        goal_label: null,
        scope: request.scope ?? "world",
        goal_options: Object.entries(cat.goals).map(([goal, label]) => ({
          goal,
          label,
        })),
        filters_applied: { policy: "viable_world_v1" },
        by_line: [],
        lines_without_destinations: [],
        places: [],
        turkey: { places: [], regions: [] },
        countries: [],
        regions: [],
        explanations: { status: "absent", absence: { reason: "needs_goal" } },
        footer: "",
      });
    if (request.goal !== "overall" && !Object.hasOwn(cat.goals, request.goal))
      throw Object.assign(new Error("Invalid goal"), { statusCode: 400 });
    if (
      request.filters?.max_distance_km != null &&
      (!Number.isFinite(request.filters.max_distance_km) ||
        request.filters.max_distance_km < 0)
    )
      throw Object.assign(new Error("Invalid distance"), { statusCode: 400 });
    const current =
      (profile.is_self
        ? (await this.store.get("me"))?.current_place
        : profile.current_place) ?? profile.birth.place;
    const value = await runReadingBridge("map_bridge.py", {
      chart: await this.store.get("raw:" + profile.profile_id),
      mode: "recommend",
      request,
      home: [current.lat, current.lon],
    });
    if (value.invalid_scope)
      throw Object.assign(new Error("Unknown country"), { statusCode: 400 });
    const mapped = mapRecommendation(
      fileURLToPath(new URL("../../", import.meta.url)),
      lang,
      cat,
      value.raw,
    );
    const f = value.raw.filters_applied;
    return validate<Recommendation>("Recommendation", {
      ...mapped,
      recommendation_id: id,
      filters_applied: {
        ...mapped.filters_applied,
        ...(f.regions?.includes("all") ? {} : { regions: f.regions }),
        purpose: f.purpose?.length === 1 ? f.purpose[0] : "both",
      },
      explanations: { status: "absent", absence: { reason: "not_generated" } },
    });
  }
  async area(
    profile: BirthProfile,
    kind: "country" | "region",
    code: string,
    lang: Lang,
  ): Promise<AreaReport> {
    if (!code || code.length > 100)
      throw Object.assign(new Error("Invalid area"), { statusCode: 400 });
    const chart = await this.store.get("raw:" + profile.profile_id);
    const value = await runReadingBridge("map_bridge.py", {
      chart,
      mode: "area",
      kind,
      code,
    });
    if (value.missing)
      throw Object.assign(new Error("Area not found"), { statusCode: 404 });
    const a = value.area,
      cat = fixture(`catalogue.${lang}`);
    if (a.status !== "ok")
      throw Object.assign(new Error("Area unavailable"), { statusCode: 503 });
    const label = (item: any) =>
      lang === "tr" ? (item.name_tr ?? item.name) : item.name;
    return validate<AreaReport>("AreaReport", {
      area: { kind, id: code, iso2: a.iso_a2, name: label(a) },
      status: "ok",
      bands: Object.fromEntries(
        Object.entries(a.bands).map(([g, v]: any) => [
          g,
          { band: v.band, label: cat.place_bands[v.band] },
        ]),
      ),
      lines_crossing: a.lines_crossing.map((l: any) => ({
        body: l.body,
        angle: l.angle,
        planet_label: cat.bodies[l.body],
        angle_label: cat.angles[l.angle].line,
      })),
      best_cities: Object.fromEntries(
        Object.entries(a.best_cities).map(([g, items]: any) => [
          g,
          items.map((c: any) => ({
            place_id: c.id,
            name: label(c),
            band: c.band,
            band_label: cat.place_bands[c.band],
          })),
        ]),
      ),
      varies_by_region: a.varies_by_region,
      ...(kind === "country"
        ? {
            regions: value.regions.map((r: any) => ({
              admin1_id: r.admin1_id,
              name: label(r),
            })),
          }
        : {}),
      overview: { status: "absent", absence: { reason: "not_generated" } },
      footer: value.footer[lang],
    });
  }
  async placeReport(
    profile: BirthProfile,
    place: PlaceReport["place"],
    lang: Lang,
    focus?: string,
  ): Promise<PlaceReport> {
    if (
      !Number.isFinite(place.lat) ||
      !Number.isFinite(place.lon) ||
      Math.abs(place.lat) > 90 ||
      Math.abs(place.lon) > 180 ||
      (focus && !Object.hasOwn(fixture("catalogue.en").goals, focus))
    )
      throw Object.assign(new Error("Invalid place request"), {
        statusCode: 400,
      });
    const chart = await this.store.get("raw:" + profile.profile_id);
    if (!chart)
      throw Object.assign(new Error("Chart unavailable"), { statusCode: 503 });
    const result = await runReadingBridge("map_bridge.py", {
      chart,
      mode: "place",
      place,
      focus_goal: focus || null,
    });
    return validate<PlaceReport>("PlaceReport", result.reports[lang]);
  }
  async heat(profile: BirthProfile, goal: string): Promise<AcgHeat> {
    if (!Object.hasOwn(fixture("catalogue.en").goals, goal))
      throw Object.assign(new Error("Unknown map goal"), { statusCode: 400 });
    const chart = await this.store.get("raw:" + profile.profile_id);
    if (!chart)
      throw Object.assign(new Error("Chart unavailable"), { statusCode: 503 });
    // The approved engine owns the persistent cache and fingerprints its code, grid and affinity data.
    const result = await runReadingBridge("map_bridge.py", {
      chart,
      mode: "heat",
      goal,
    });
    return validate<AcgHeat>("AcgHeat", {
      chart_key: profile.chart_key,
      goal: result.goal,
      grid_step_deg: result.grid_step_deg,
      points: result.points,
    });
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
