// Generated from FE_02 and FE_09 by scripts/build-contract.ts.
import type * as GeoJSON from 'geojson';
export type Lang = 'tr' | 'en';
export type ISODate = string;          // 'YYYY-MM-DD' local
export type LocalTime = string;        // 'HH:mm'
export type ISODateTime = string;

export type Body = 'sun' | 'moon' | 'mercury' | 'venus' | 'mars' | 'jupiter' | 'saturn'
          | 'uranus' | 'neptune' | 'pluto' | 'north_node' | 'south_node';
export type Angle = 'ASC' | 'DSC' | 'MC' | 'IC';
export type Sign = 'aries' | 'taurus' | 'gemini' | 'cancer' | 'leo' | 'virgo'
          | 'libra' | 'scorpio' | 'sagittarius' | 'capricorn' | 'aquarius' | 'pisces';
export type AspectType = 'conjunction' | 'sextile' | 'square' | 'trine' | 'opposition';

export type Goal = 'love' | 'career' | 'business' | 'money' | 'family' | 'education'
          | 'creativity' | 'spirituality' | 'rest' | 'travel' | 'relocation';      // ACG_08 §1, CAL_00 D8
export type PlaceBand = 'strongly_supportive' | 'supportive' | 'mixed' | 'no_emphasis' | 'challenging';  // ACG_08 §4
export type DayBand = 'strongly_supportive' | 'supportive' | 'quiet' | 'mixed'
             | 'challenging' | 'strongly_challenging';                                  // calendar day_scores
export type DayTone = 'favorable' | 'mixed' | 'quiet' | 'challenging';
export type Activity = 'love' | 'meetings' | 'business' | 'contract' | 'conversation'
              | 'travel' | 'shopping' | 'project_start' | 'interview' | 'moving';       // CAL_04
export type Grade = 'excellent' | 'good' | 'neutral' | 'avoid';
export type Importance = 'major' | 'moderate' | 'minor' | 'collective';
export type MoonPhase = 'new' | 'waxing_crescent' | 'first_quarter' | 'waxing_gibbous'
               | 'full' | 'waning_gibbous' | 'last_quarter' | 'waning_crescent';
export type Lens = 'general' | 'personal' | 'professional';     // forecast "profile"; UI: General · Love & relationships · Work & career
export type CompatType = 'love' | 'family' | 'work';
export type FamilyRelation = 'parent_child' | 'siblings' | 'other';
export type Relation = 'self' | 'partner' | 'child' | 'parent' | 'family' | 'friend'
              | 'colleague' | 'business_partner' | 'other';
export type Tier = 'tight' | 'strong' | 'wide';
export type TransitPhase = 'building' | 'peak' | 'easing';

export interface Place {
  place_id: string;
  name: string;                 // in `lang` (name_tr for tr when available)
  admin1: string | null;        // province / state
  country_code: string;         // ISO-3166-1 alpha-2
  country_name: string;
  lat: number; lon: number;
  tz: string;                   // IANA
}

export interface Job {
  job_id: string;
  kind: 'natal_section' | 'dossier' | 'natal_reading' | 'element_notes' | 'day_reading' | 'month_reading' | 'year_reading'
      | 'solar_return' | 'compatibility' | 'place_reading' | 'area_reading' | 'recommendation'
      | 'calendar_text' | 'best_day_text';
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  stages: { name: JobStage; status: 'pending' | 'running' | 'ok' | 'skipped' | 'failed' }[];
  created_at: ISODateTime; updated_at: ISODateTime;
  eta_seconds: number | null;     // best guess from recent jobs of the same kind; may be null
  error: Problem | null;
}

export type JobStage = string;          // manifest stage names; known values in §4.3, unknown → "Preparing"

export type GeneratedPart<T> =
  | ({ status: 'ready' } & T)
  | { status: 'pending'; job: Job }
  | { status: 'failed'; error: Problem }
  | { status: 'absent'; absence: Absence };

export interface Problem {
  type: string; title: string; status: number;
  code: 'validation_error' | 'unauthorized' | 'forbidden' | 'not_found' | 'conflict'
      | 'out_of_range' | 'rate_limited' | 'generation_failed' | 'absent'
      | 'upstream_unavailable' | 'internal' | 'busy' | 'account_required' | 'read_ahead_limit';
  blocking_job_id?: string;
  detail?: string;                               // developer text, never shown to users
  fields?: { field: string; issue: string }[];   // validation_error
  absence?: Absence;                             // code = 'absent'
}
export interface Absence { reason: AbsenceReason; stage?: string }
export type AbsenceReason = 'time_not_exact' | 'placidus_undefined_high_latitude' | 'acg_corpus_missing'
                   | 'no_grounding' | 'place_not_found' | (string & {});   // open set, §5.2

export interface Session {
  access_token: string; access_expires_at: ISODateTime;
  refresh_token: string;
  is_new_user: boolean;
  me: Me;
}

export interface Me {
  user_id: string;
  email: string | null;
  display_name: string;                     // writable
  language: Lang;                           // writable
  theme: 'system' | 'light' | 'dark';       // writable
  current_place: Place | null;              // writable via current_place_id; drives "today" (F10)
  self_profile_id: string | null;
  notification_prefs: NotificationPrefs;    // writable
  entitlements: Record<string, true>;       // all true in v1 (F4)
  ask_quota: { limit_per_day: number; used_today: number; resets_at: ISODateTime };
  consents: { birth_data: { version: string; accepted_at: ISODateTime } | null;
              marketing: boolean };         // writable (accept via PATCH { consents: {...} })
  created_at: ISODateTime;
}
export interface NotificationPrefs {
  enabled: boolean;
  types: Record<NotificationType, boolean>;  // default all true
  time: LocalTime;                           // default '09:00'
  max_per_day: number;                       // default 1
  max_per_week: number;                      // default 3
  quiet_hours: { start: LocalTime; end: LocalTime };   // default 22:00–08:00
}
export type NotificationType = 'favorable_window' | 'period_start' | 'lunation_in_house'
                      | 'retrograde_start' | 'station_on_point' | 'eclipse_hit';

export interface PlaceCandidate extends Place {
  kind: 'city' | 'town' | 'village' | 'district' | 'region' | 'country' | 'destination';
  population: number | null;
  source: 'gazetteer' | 'destination' | 'geocoder';
}
// kind=area results: { place_id: 'iso2:TR' | 'admin1:TUR-…', kind: 'country'|'region', name, country_code, … }

export interface BirthProfileInput {
  label: string;                       // 1–40 chars, as the user typed it
  relation: Relation;                  // exactly one profile per user has 'self'
  birth_date: ISODate;                 // 1900-01-01 … today
  birth_time: LocalTime;               // exact time required (F9)
  birth_place_id: string;              // from /places/search?kind=birth
  gender?: 'female' | 'male' | 'other' | null;       // optional (brief §2); not used by readings
  current_place_id?: string | null;    // optional, for other people; self uses me.current_place
}
export interface BirthProfile {
  profile_id: string; chart_key: string;
  label: string; relation: Relation; is_self: boolean;
  birth: { date: ISODate; time: LocalTime; place: Place; tz: string; utc: ISODateTime };
  gender: 'female' | 'male' | 'other' | null;
  current_place: Place | null;
  big_three: { sun: Sign; moon: Sign; ascendant: Sign };    // DERIVED from chart.json
  natal_reading_job?: Job;                                  // only on POST of the self profile
  created_at: ISODateTime; updated_at: ISODateTime;
}

export interface ChartData {
  profile_id: string; chart_key: string;
  utc: ISODateTime; tz: string;
  points: ChartPoint[];          // 12: ten planets + both nodes, in chart.json order
  axes: { asc: AxisPoint; mc: AxisPoint };
  houses: House[];               // 12
  aspects: Aspect[];
}
export interface ChartPoint { body: Body; longitude: number; sign: Sign; degree_in_sign: number;
                       house: number; retrograde: boolean }
export interface AxisPoint { longitude: number; sign: Sign; degree_in_sign: number }
export interface House { house: number; cusp_longitude: number; sign: Sign;
                  rulers: Body[]; planets: Body[] }
export interface Aspect { a: Body; b: Body; type: AspectType; orb: number }

export interface NatalReading {
  profile_id: string; chart_key: string; lang: Lang; generated_at: ISODateTime;
  title: string;                                        // l4_render _DOC_TITLE
  parts: { movement: 1 | 2; title: string }[];          // l4_render MOVEMENT_TITLES
  sections: NatalSection[];                             // l4_output order; empty ones already omitted
}
export interface NatalSection {
  key: 'core_identity' | 'sun_house' | 'moon_house' | 'inner_drives' | 'chart_shape'
     | 'identity' | 'values_money' | 'communication_learning' | 'family_home'
     | 'joy_creativity_children' | 'health_routine_pets' | 'partnerships'
     | 'transformation_intimacy' | 'travel_philosophy' | 'status_vocation'
     | 'friendships_future' | 'subconscious_solitude';
  movement: 1 | 2;
  house: number | null;
  title: string;          // l4_render.section_title(key, lang, house)
  text: string;           // text_tr | text_en; paragraphs separated by blank lines
}

export interface ChartElements {
  chart_key: string; lang: Lang;
  bodies: Partial<Record<Body, ElementNote>>;
  houses: Partial<Record<'1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9'|'10'|'11'|'12', ElementNote>>;
  signs: Partial<Record<Sign, ElementNote>>;
  aspects: { a: Body; b: Body; type: AspectType; note: ElementNote }[];
}
export interface ElementNote { text: string; section_key: NatalSection['key'] | null }

export interface DayForecast {
  profile_id: string; date: ISODate; tz: string; lens: Lens;
  tone: DayTone; tone_label: string; score_10: number;             // §6.2
  areas: Record<Goal, DayArea>;                                     // all 11
  moon: MoonInfo;
  retrograde: Body[];
  events: CalendarEventRef[];                                       // the day's calendar events
  transits: TransitEpisode[];                                       // episodes active on `date`, importance major|moderate
  reading: GeneratedPart<{ text: string }>;                         // 120–180 words
  day_note: GeneratedPart<{ text: string }> | null;                 // CAL_03 day_note (40–60 words)
  best_activities: { activity: Activity; label: string; grade: 'excellent' | 'good' }[];  // Best Days on `date`
  domains?: { key: 'love' | 'family' | 'work' | 'money' | 'communication' | 'emotions';
              title: string; text: string }[];                      // NEW, optional (F13)
  advice?: string;                                                  // NEW, optional (F13)
}
export interface DayArea { band: DayBand; label: string; score_10: number; drivers: string[] /* transit labels */ }
export interface MoonInfo { phase: MoonPhase; phase_label: string; sign: Sign; sign_label: string;
                     void_of_course: { start: LocalTime; end: LocalTime }[] }
export interface CalendarEventRef { id: string; kind: CalendarItemKind; label: string;
                             importance: Importance; has_text: boolean }
export interface TransitEpisode {
  id: string; label: string; importance: Importance;
  transiting: Body; aspect: AspectType; natal: Body | Angle;
  start: ISODate; end: ISODate; exact_dates: ISODate[];
  phase: TransitPhase; phase_label: string;                         // relative to the request date, §6.3
  has_text: boolean;
}

export interface HomeSummary {
  date: ISODate; tz: string; greeting_name: string;       // display_name or self label
  tone: DayTone; tone_label: string; score_10: number;
  tiles: { key: Goal | 'energy'; label: string; band: DayBand; score_10: number }[];
        // love, career, money, family (O2; 'energy' only if flag homeEnergyTile and backend provides it)
  moon: MoonInfo;
  today: GeneratedPart<{ text: string }>;                  // = day reading, general lens
  next_up: UpcomingItem[];                                 // ≤ 3, next 14 days
}
export interface UpcomingItem {
  kind: 'period_start' | 'lunation' | 'eclipse' | 'retrograde_start' | 'best_window' | 'transit_peak';
  date: ISODate; label: string;
  deep_link: { view: 'best_days' | 'period' | 'event'; ref: string };
}

export interface MonthForecast {
  profile_id: string; month: string; tz: string; lens: Lens;
  segments: { early: DateRange; mid: DateRange; late: DateRange };   // the backend's beat split (expected 1–10, 11–20, 21–end; backend confirms)
  reading: GeneratedPart<{ overview: string; early: string; mid: string; late: string;
                           focus: string; focus_title: string }>;
  highlights: {
    favorable_days: ISODate[];          // calendar days with tone 'favorable'
    challenging_days: ISODate[];        // tone 'challenging'
    periods: PeriodRef[];               // periods overlapping the month
    major_transits: TransitEpisode[];   // calendar month `major_transits` (+ phase at mid-month)
    lunations: CalendarEventRef[];
    eclipses: CalendarEventRef[];
    retrogrades: RetrogradeRef[];
  };
  domains?: { key: 'love' | 'family' | 'work' | 'career' | 'money' | 'social' | 'travel';
              title: string; text: string }[];                       // NEW, optional (brief §7)
}
export interface DateRange { from: ISODate; to: ISODate }
export interface PeriodRef { id: string; goal: Goal; goal_label: string; kind: 'favorable' | 'challenging';
                      label: string; start: ISODate; end: ISODate; peak: ISODate;
                      strength: 'normal' | 'strong'; importance: Importance; has_text: boolean }
export interface RetrogradeRef { id: string; body: Body; label: string; start: ISODate; end: ISODate }

export interface YearForecast {
  profile_id: string; from: string; to: string; tz: string; lens: Lens;
  quarters: { key: 'q1' | 'q2' | 'q3' | 'q4'; from: ISODate; to: ISODate }[];
  reading: GeneratedPart<{ overview: string; q1: string; q2: string; q3: string; q4: string;
                           focus: string; focus_title: string }>;
  highlights: {
    strongest_periods: PeriodRef[];      // favorable, importance major or strength strong, ≤ 6
    challenging_periods: PeriodRef[];    // challenging, importance major or strength strong, ≤ 6
    key_events: CalendarEventRef[];      // eclipses, Jupiter–Pluto ingresses, major transits (12 months)
    retrogrades: RetrogradeRef[];
  };
  months: { month: string; label: string }[];   // 12 entries → each opens MonthForecast (generated lazily)
  domains?: { key: 'growth' | 'love' | 'family' | 'career' | 'business' | 'money'
                  | 'home_property' | 'travel' | 'social'; title: string; text: string }[];  // NEW, optional (brief §8)
}

export interface SolarReturn {
  profile_id: string; year: number; return_utc: ISODateTime; place: Place;
  chart: ChartData;                                     // same shape as §7.2
  reading: GeneratedPart<{ sections: { key: string; title: string; text: string }[] }>;
}

export interface Compatibility {
  compatibility_id: string; type: CompatType; family_relation: FamilyRelation | null;
  people: { a: PersonRef; b: PersonRef };
  created_at: ISODateTime;
  reading: GeneratedPart<{ title: string; sections: CompatSection[] }>;
  score: null | { value: number; label: string };   // always null in v1 (O1; S3 §6 no-score)
}
export interface PersonRef { profile_id: string; label: string; big_three: BirthProfile['big_three'] }
export interface CompatSection { key: string; movement: number; title: string; text: string }
export interface CompatibilitySummary { compatibility_id: string; type: CompatType;
  people: { a: PersonRef; b: PersonRef }; status: 'ready' | 'pending' | 'failed'; created_at: ISODateTime }

export interface AcgLines {
  chart_key: string;
  lines: GeoJSON.FeatureCollection<GeoJSON.MultiLineString,
          { body: Body; angle: Angle; read: boolean }>;            // acg.geojson; read_in_v1 → read
  parans: GeoJSON.FeatureCollection<GeoJSON.LineString,
          { id: string; bodies: [Body, Body]; angles: [Angle, Angle] }>;   // acg_parans.geojson
}

export interface AcgHeat {
  chart_key: string; goal: Goal; grid_step_deg: number;          // 0.5
  points: [lon: number, lat: number, level: 2 | 1 | 0 | -1][];   // 2 strongly_supportive, 1 supportive, 0 mixed, -1 challenging
}

export interface LinePlaces {
  line: { body: Body; angle: Angle; planet_label: string; angle_label: string };
  places: { place_id: string; name: string; country_code: string;
            distance_km_rounded: number | '<10'; tier: Tier; tier_label: string }[];
}

export interface PlaceReport {
  place: { place_id: string | null; name: string; country_code: string | null; lat: number; lon: number };
  status: 'ok' | 'absent'; absence?: Absence;
  relocation: { status: 'ok' | 'absent'; absence?: Absence };
  focus_goal: Goal | null;
  lines_display: LineDisplay[];            // immediate
  parans_display: ParanDisplay[];          // immediate
  goal_scores: Record<Goal, { band: PlaceBand; label: string }>;   // immediate
  cards: SuitabilityCard[];                // immediate bands; text pending until the reading is ready
  reading: GeneratedPart<{ sections: PlaceSection[] }>;
  footer: string;                          // fixed ACG footer (ACG_04 §6)
}
export interface LineDisplay { body: Body; angle: Angle; planet_label: string; angle_label: string;
  distance_km_rounded: number | '<10'; tier: Tier; tier_label: string; read_in_prose: boolean }
export interface ParanDisplay { id: string; bodies: [Body, Body]; planet_labels: [string, string];
  north_south: 'north' | 'south'; distance_km_rounded: number | '<10'; label: string }
export interface SuitabilityCard { card: 'travel' | 'living' | 'work' | 'business' | 'love' | 'family' | 'focus';
  goal: Goal; title: string; band: PlaceBand; band_label: string;
  text: string | null }        // no_emphasis: fixed template text at once; others: null until reading ready
export interface PlaceSection { key: string; title: string; paragraphs: { slot_id: string; text: string }[] }

export interface AreaReport {
  area: { kind: 'country' | 'region'; id: string; iso2: string; name: string };
  status: 'ok' | 'absent'; absence?: Absence;
  bands: Record<Goal, { band: PlaceBand; label: string }>;          // bands[g].band (drop S_agg, P_agg, N_agg, k)
  lines_crossing: { body: Body; angle: Angle; planet_label: string; angle_label: string }[];
  best_cities: Record<Goal, { place_id: string; name: string; band: PlaceBand; band_label: string }[]>;  // top 3
  varies_by_region: boolean;
  regions?: { admin1_id: string; name: string }[];                  // countries only
  overview: GeneratedPart<{ text: string }>;                        // place_overview, 90–140 words
  footer: string;
}

export interface RecommendationRequest {
  goal?: Goal | 'overall';
  query_text?: string;                       // free text (ACG_09 §2) when goal is absent
  scope?: 'world' | string;                  // 'world' (default) or ISO-2 ('TR', 'DE', …)
  filters?: {
    regions?: ('europe' | 'turkey' | 'mediterranean' | 'middle_east_gulf' | 'caucasus' | 'americas'
             | 'east_asia' | 'south_southeast_asia' | 'oceania' | 'central_asia')[];
    city_size?: ('big' | 'mid' | 'small')[];
    max_distance_km?: number | null;
    climate?: ('warm' | 'mild' | 'cold')[] | null;
    purpose?: 'living' | 'travel' | 'both';
  };
}
export interface Recommendation {
  recommendation_id: string;
  status: 'ok' | 'thin_result' | 'needs_goal';
  goal: Goal | 'overall' | null; goal_label: string | null; scope: string;
  goal_options?: { goal: Goal; label: string }[];      // needs_goal only
  filters_applied: RecommendationRequest['filters'] & { policy: string };
  by_line: {
    group_id: string; kind: 'line' | 'paran';
    line: { body: Body; angle: Angle } | { bodies: [Body, Body]; angles: [Angle, Angle] };
    title: string;                                     // e.g. "Jupiter · Culminating line" (labels from catalogue)
    destinations: Destination[];
  }[];
  lines_without_destinations: { line: { body: Body; angle: Angle }; title: string; text: string }[];
  places: Destination[];                               // flat top list (ACG_11 §5.6); for 'overall' the ranked list
  turkey: { places: Destination[]; regions: AreaRef[] };
  countries: AreaRef[]; regions: AreaRef[];
  explanations: GeneratedPart<{ intro: string; turkey_intro: string | null;
                                 groups: Record<string, string>; items: Record<string, string> }>;
  footer: string;
}
export interface Destination {
  place_id: string; name: string; country_code: string; size: 'big' | 'mid' | 'small';
  band: PlaceBand; band_label: string;
  summary_label?: string;                              // 'overall': e.g. "Supportive for 7 goals"
  dominant_line: { body: Body; angle: Angle; distance_km_rounded: number | '<10' } | null;
  has_tradeoff: boolean;
  purposes: ('living' | 'travel')[];
  lat: number; lon: number;
}
export interface AreaRef { id: string; kind: 'country' | 'region'; name: string; band: PlaceBand; band_label: string }

export type CalendarItemKind = 'transit' | 'lunation' | 'eclipse' | 'station' | 'station_on_point'
                      | 'ingress' | 'retrograde_period' | 'period';
export interface CalendarMonth {
  profile_id: string; month: string; tz: string;
  days: CalendarDay[];
  lunations: CalendarEventRef[]; eclipses: CalendarEventRef[];
  retrograde_periods: RetrogradeRef[]; major_transits: TransitEpisode[]; periods: PeriodRef[];
}
export interface CalendarDay {
  date: ISODate; tone: DayTone; tone_label: string;
  moon: MoonInfo; retrograde: Body[];
  events: CalendarEventRef[];
  active_periods: { id: string; goal: Goal; kind: 'favorable' | 'challenging' }[];
  goals: Record<Goal, DayBand>;
}
export interface CalendarDayDetail extends CalendarDay {
  day_note: GeneratedPart<{ text: string }> | null;
  transits: TransitEpisode[];                                    // active episodes (as in DayForecast)
  best_activities: { activity: Activity; label: string; grade: 'excellent' | 'good' }[];   // from best_days
}
export interface CalendarItem {
  id: string; kind: CalendarItemKind; label: string; importance: Importance;
  start?: ISODate; end?: ISODate; peak?: ISODate; exact_dates?: ISODate[];
  transiting?: Body; aspect?: AspectType; natal?: Body | Angle;           // transit, station_on_point
  goal?: Goal; goal_label?: string; period_kind?: 'favorable' | 'challenging';
  strength?: 'normal' | 'strong';                                         // period
  sign?: Sign; natal_house?: number; house_label?: string;                // lunation / eclipse
  lunation_kind?: 'new' | 'full'; eclipse_kind?: 'solar' | 'lunar';
  body?: Body;                                                            // station / retrograde / ingress
  text: GeneratedPart<{ text: string }> | null;    // null = label only by design (CAL_03: minor transits, no grounding)
}
export interface CalendarYear {
  horizon: DateRange; lunations: CalendarEventRef[]; eclipses: CalendarEventRef[];
  retrograde_periods: RetrogradeRef[]; major_transits: TransitEpisode[]; periods: PeriodRef[];
}

export interface BestDaysOverview {
  horizon: DateRange; tz: string;
  activities: {
    activity: Activity; label: string;
    days: { date: ISODate; grade: Grade }[];          // every day of the horizon
    top_days: ISODate[];
    windows: { start: ISODate; end: ISODate; days: number }[];
    avoid_days: ISODate[];
  }[];                                                 // 10, in the catalogue order
}
export interface BestDayDetail {
  activity: Activity; activity_label: string; date: ISODate; grade: Grade; grade_label: string;
  reasons: { positive: string[]; negative: string[] };    // label_tr/en of reasons[date], ordered by contribution
  text: GeneratedPart<{ text: string }> | null;
}
export interface NotificationCandidate {
  id: string; type: NotificationType; priority: 1 | 2 | 3;
  trigger_date: ISODate; suggested_time: LocalTime;
  text: string;                                            // text_tr | text_en
  deep_link: { view: 'best_days' | 'period' | 'event'; ref: string };
}

export interface ReportRef {
  report_id: string;
  type: 'natal' | 'compatibility' | 'place' | 'area' | 'recommendation'
      | 'forecast_month' | 'forecast_year' | 'solar_return';
  title: string; subtitle: string;          // e.g. "İzmir" / "Ayşe · 30 Eyl 2026"
  profile_id: string; created_at: ISODateTime;
  route: string;                            // app path to open it, e.g. "/map?place=gn-311046"
}

export interface Catalogue {
  version: string; lang: Lang;
  bodies: Record<Body, string>;                          // "Güneş", "Kuzey Ay Düğümü" …
  angles: Record<Angle, { short: string; name: string; line: string }>;   // AC/Yükselen/Yükselen çizgi …
  signs: Record<Sign, string>;
  aspects: Record<AspectType, string>;
  houses: Record<string, { ordinal: string; name: string }>;   // "9": { "9. Ev", "Uzak Seyahatler ve Felsefe" }
  goals: Record<Goal, string>;
  place_bands: Record<PlaceBand, string>; day_bands: Record<DayBand, string>;
  tones: Record<DayTone, string>; grades: Record<Grade, string>;
  activities: Record<Activity, string>;
  lenses: Record<Lens, string>; lens_focus_titles: Record<Lens, string>;
  compat_types: Record<CompatType, string>; family_relations: Record<FamilyRelation, string>;
  relations: Record<Relation, string>;
  moon_phases: Record<MoonPhase, string>;
  transit_phases: Record<TransitPhase, string>;
  tiers: Record<Tier, string>;
  notification_types: Record<NotificationType, string>;
  recommend_regions: Record<string, string>;             // filter chips
  city_sizes: Record<'big' | 'mid' | 'small', string>; climates: Record<'warm' | 'mild' | 'cold', string>;
  purposes: Record<'living' | 'travel' | 'both', string>;
  terms: {                                               // short astro terms used as UI labels
    retrograde: string;                                  // "Retro" / "Retrograde"
    void_of_course: string;                              // "Boşlukta Ay" / "Void-of-course Moon"
    new_moon: string; full_moon: string; solar_eclipse: string; lunar_eclipse: string;
    solar_return: string; rising: string; big_three: string;
  };
}

export interface Config {
  min_app_version: { ios: string; android: string };    // force-update below
  flags: Record<string, boolean>;                       // FE_01 §3.6
  polling: { initial_ms: number[]; interval_ms: number; slow_after_s: number; give_up_after_s: number };
  map_style_url: { light: string; dark: string };
  links: { privacy: string; terms: string; support: string };
}

export interface AskRequest { text: string; context?: AskContext }
export interface AskContext {
  date?: ISODate; month?: string; place_id?: string; other_profile_id?: string;
  compatibility_id?: string; item_id?: string; activity?: Activity; section_key?: string;
}

export type AskCard =
  | { type: 'chart_fact'; body: Body; sign: Sign; degree_in_sign: number; house: number; retrograde: boolean }
  | { type: 'best_days'; activity: Activity; days: { date: ISODate; grade: Grade }[] }
  | { type: 'place'; place_id: string; name: string; country_code: string;
      cards: { goal: Goal; band: PlaceBand; band_label: string }[] }
  | { type: 'period'; period: PeriodRef }
  | { type: 'transit'; transit: TransitEpisode }
  | { type: 'compatibility'; compatibility_id: string; labels: [string, string]; compat_type: CompatType }
  | { type: 'forecast'; horizon: 'day' | 'month' | 'year'; date?: ISODate; month?: string; title: string };

export interface Thread { thread_id: string; profile_id: string; title: string;
                   created_at: ISODateTime; updated_at: ISODateTime; messages?: Message[] }
export interface Message { message_id: string; role: 'user' | 'assistant'; text: string;
                    cards: AskCard[]; links: { label: string; route: string }[];
                    status: 'complete' | 'interrupted' | 'failed'; feedback?: 'up' | 'down';
                    created_at: ISODateTime }

export interface ReadingOutline {
  profile_id: string; chart_key: string; lang: Lang; title: string;
  parts: { movement: 1 | 2; title: string }[];
  sections: { key: NatalSection['key']; movement: 1 | 2; house: number | null; title: string;
    status: 'not_started' | 'generating' | 'ready' | 'failed'; access: 'open' | 'account_required' }[];
  big_three: { sun: Sign; moon: Sign; rising: Sign };
  accuracy: { score: number; n: number } | null;
}
export interface ReadingProgressInput { key: NatalSection['key']; event: 'opened' | 'finished' }
export interface ReadingFeedbackInput {
  profile_id: string; target: { type: 'reading' | 'section' | 'big_three'; key?: string };
  rating: 'spot_on' | 'partly' | 'not_me'; comment?: string;
}
export interface ReadingAccuracy { accuracy: { score: number; n: number } }

export interface EmailStart { email: string; lang: Lang }
export interface EmailVerify { email: string; code: string }
export interface AppleSignIn { identity_token: string; authorization_code: string; full_name?: string }
export interface GoogleSignIn { id_token: string }
export interface RefreshSession { refresh_token: string }
export type MeInput = Partial<Pick<Me,'display_name'|'language'|'theme'|'notification_prefs'|'consents'>> & { current_place_id?: string | null };
export type BirthProfilePatch = Partial<BirthProfileInput>;
export type PlaceOrNull = Place | null;
export interface CompatibilityInput { profile_a_id: string; profile_b_id: string; type: CompatType; family_relation?: FamilyRelation }
export interface CompatibilityPage { items: CompatibilitySummary[]; next_cursor: string | null }
export interface ThreadInput { profile_id: string }
// FE_02 names ThreadSummary without defining it. Proposal recorded in exploration report.
export type ThreadSummary = Omit<Thread, 'messages'>;
export interface ThreadPage { items: ThreadSummary[]; next_cursor: string | null }
export interface FeedbackInput { rating: 'up' | 'down'; reason?: string }
export interface ReportPage { items: ReportRef[]; next_cursor: string | null }
export interface JobAccepted { job: Job }
export interface GenerationAbsent { status: "absent"; absence: Absence }
export type CountryGeometry = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, { iso2: string; name_tr: string; name_en: string }>;
export type RegionGeometry = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, { admin1_id: string; iso2: string; name_tr: string; name_en: string }>;
