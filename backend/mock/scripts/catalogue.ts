import type { Catalogue, Lang } from "../../../frontend/contracts/spec-types";
const names = (keys: string, tr: string, en: string, lang: Lang) =>
  Object.fromEntries(
    keys
      .split("|")
      .map((key, i) => [key, (lang === "tr" ? tr : en).split("|")[i]]),
  );
export function catalogue(lang: Lang, backend: any): Catalogue {
  const pair = (keys: string, tr: string, en: string) =>
    names(keys, tr, en, lang);
  const houses = Object.fromEntries(
    Object.entries(backend.natal[lang].sections)
      .slice(5)
      .map(([_, value]: any, i) => [
        String(i + 1),
        {
          ordinal: lang === "tr" ? `${i + 1}. Ev` : `House ${i + 1}`,
          name: value["0"].split(" — ").at(-1),
        },
      ]),
  );
  return {
    version: "fe-v1",
    lang,
    bodies: {
      ...backend.bodies[lang],
      ...pair(
        "north_node|south_node",
        "Kuzey Ay Düğümü|Güney Ay Düğümü",
        "North Node|South Node",
      ),
    },
    signs: backend.signs[lang],
    houses,
    angles: Object.fromEntries(
      ["ASC", "DSC", "MC", "IC"].map((key, i) => [
        key,
        {
          short: ["AC", "DC", "MC", "IC"][i],
          name: (lang === "tr"
            ? ["Yükselen", "Alçalan", "Tepe Noktası", "Dip Noktası"]
            : ["Ascendant", "Descendant", "Midheaven", "IC"])[i],
          line: (lang === "tr"
            ? ["Yükselen çizgi", "Alçalan çizgi", "Tepe çizgisi", "Dip çizgisi"]
            : [
                "Rising line",
                "Setting line",
                "Culminating line",
                "Lower line",
              ])[i],
        },
      ]),
    ) as Catalogue["angles"],
    aspects: pair(
      "conjunction|sextile|square|trine|opposition",
      "Kavuşum|Altmışlık|Kare|Üçgen|Karşıt",
      "Conjunction|Sextile|Square|Trine|Opposition",
    ) as Catalogue["aspects"],
    goals: Object.fromEntries(
      Object.entries(backend.goals).map(([k, v]: any) => [
        k,
        v[lang === "tr" ? 0 : 1],
      ]),
    ) as Catalogue["goals"],
    day_bands: pair(
      "strongly_supportive|supportive|quiet|mixed|challenging|strongly_challenging",
      "Çok destekleyici|Destekleyici|Sakin|Karma|Zorlayıcı|Çok zorlayıcı",
      "Strongly supportive|Supportive|Quiet|Mixed|Challenging|Strongly challenging",
    ) as Catalogue["day_bands"],
    place_bands: pair(
      "strongly_supportive|supportive|mixed|no_emphasis|challenging",
      "Çok destekleyici|Destekleyici|Karma|Belirgin bir vurgu yok|Zorlayıcı",
      "Strongly supportive|Supportive|Mixed|No clear emphasis|Challenging",
    ) as Catalogue["place_bands"],
    tones: pair(
      "favorable|quiet|mixed|challenging",
      "Destekleyici|Sakin|Karma|Zorlayıcı",
      "Supportive|Quiet|Mixed|Challenging",
    ) as Catalogue["tones"],
    grades: pair(
      "excellent|good|neutral|avoid",
      "Çok uygun|Uygun|Nötr|Dikkat gerektiren",
      "Excellent|Good|Neutral|Avoid",
    ) as Catalogue["grades"],
    activities: pair(
      "love|meetings|business|contract|conversation|travel|shopping|project_start|interview|moving",
      "Aşk|Görüşmeler|İş|Sözleşme imzalama|Önemli konuşma|Seyahat|Alışveriş|Projeye başlama|İş görüşmesi|Taşınma",
      "Love|Meetings|Business|Signing a contract|Important conversation|Travel|Shopping|Starting a project|Job interview|Moving",
    ) as Catalogue["activities"],
    lenses: pair(
      "general|personal|professional",
      "Genel|Aşk ve ilişkiler|İş ve kariyer",
      "General|Love & relationships|Work & career",
    ) as Catalogue["lenses"],
    lens_focus_titles: pair(
      "general|personal|professional",
      "Dönemin odağı|Aşk ve ilişkiler|İş ve kariyer",
      "Focus of the period|Love & relationships|Work & career",
    ) as Catalogue["lens_focus_titles"],
    compat_types: pair(
      "love|family|work",
      "Aşk|Aile|İş",
      "Love|Family|Work",
    ) as Catalogue["compat_types"],
    family_relations: pair(
      "parent_child|siblings|other",
      "Ebeveyn ve çocuk|Kardeşler|Diğer",
      "Parent and child|Siblings|Other",
    ) as Catalogue["family_relations"],
    relations: pair(
      "self|partner|child|parent|family|friend|colleague|business_partner|other",
      "Ben|Partner|Çocuk|Ebeveyn|Aile|Arkadaş|İş arkadaşı|İş ortağı|Diğer",
      "You|Partner|Child|Parent|Family|Friend|Colleague|Business partner|Other",
    ) as Catalogue["relations"],
    moon_phases: pair(
      "new|waxing_crescent|first_quarter|waxing_gibbous|full|waning_gibbous|last_quarter|waning_crescent",
      "Yeni Ay|Büyüyen hilal|İlk dördün|Büyüyen şişkin Ay|Dolunay|Küçülen şişkin Ay|Son dördün|Küçülen hilal",
      "New Moon|Waxing crescent|First quarter|Waxing gibbous|Full Moon|Waning gibbous|Last quarter|Waning crescent",
    ) as Catalogue["moon_phases"],
    transit_phases: pair(
      "building|peak|easing",
      "Yaklaşıyor|Dorukta|Hafifliyor",
      "Building|Peak|Easing",
    ) as Catalogue["transit_phases"],
    tiers: pair(
      "tight|strong|wide",
      "Çok yakın|Yakın|Uzak etki alanı",
      "Very close|Close|Distant range",
    ) as Catalogue["tiers"],
    notification_types: pair(
      "favorable_window|period_start|lunation_in_house|retrograde_start|station_on_point|eclipse_hit",
      "Destekleyici günler|Dönem başlangıcı|Ay döngüleri|Retro başlangıcı|Gezegen dönüşü|Tutulmalar",
      "Supportive days|Period start|Moon cycles|Retrograde start|Planetary stations|Eclipses",
    ) as Catalogue["notification_types"],
    recommend_regions: pair(
      "europe|turkey|mediterranean|middle_east_gulf|caucasus|americas|east_asia|south_southeast_asia|oceania|central_asia",
      "Avrupa|Türkiye|Akdeniz|Orta Doğu ve Körfez|Kafkasya|Amerika|Doğu Asya|Güney ve Güneydoğu Asya|Okyanusya|Orta Asya",
      "Europe|Turkey|Mediterranean|Middle East & Gulf|Caucasus|Americas|East Asia|South & Southeast Asia|Oceania|Central Asia",
    ) as Record<string, string>,
    city_sizes: pair(
      "big|mid|small",
      "Büyük|Orta|Küçük",
      "Big|Mid-size|Small",
    ) as Catalogue["city_sizes"],
    climates: pair(
      "warm|mild|cold",
      "Sıcak|Ilıman|Soğuk",
      "Warm|Mild|Cold",
    ) as Catalogue["climates"],
    purposes: pair(
      "living|travel|both",
      "Yaşamak|Seyahat|Her ikisi",
      "Living|Travel|Both",
    ) as Catalogue["purposes"],
    terms: pair(
      "retrograde|void_of_course|new_moon|full_moon|solar_eclipse|lunar_eclipse|solar_return|rising|big_three",
      "Retro|Boşlukta Ay|Yeni Ay|Dolunay|Güneş tutulması|Ay tutulması|Güneş dönüşü|Yükselen|Üç temel gösterge",
      "Retrograde|Void-of-course Moon|New Moon|Full Moon|Solar eclipse|Lunar eclipse|Solar Return|Rising|Big three",
    ) as Catalogue["terms"],
  };
}
