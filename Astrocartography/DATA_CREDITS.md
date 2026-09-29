# Geography data credits (astrocartography layer)

The committed geography files in this folder are built from open data by
`build_geo_index.py`, `build_gazetteer.py` and `build_destinations.py` (sources are
downloaded to `.cache/geodata/`, which is not committed).

## GeoNames: CC BY 4.0 (attribution required in the app credits)

`gazetteer.json` (city names, coordinates, population, Turkish names) is derived from
[GeoNames](https://www.geonames.org/) (`cities15000`, `alternateNamesV2`,
`countryInfo`), licensed under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
The data was filtered and reformatted, and some Turkish names were set by hand (the 81
province centres, and the v1 exonyms for the diaspora cities).

`destinations.json` (spec 11: names, coordinates, population, Turkish names, and the
GeoNames match of the curated / drafted travel destinations) is also derived from GeoNames
(`cities15000`, `allCountries`, `alternateNamesV2`, `countryInfo`), CC BY 4.0.

Suggested app credit line: *"City data © GeoNames (geonames.org), CC BY 4.0."*

## WorldClim: CC BY 4.0 (attribution required in the app credits)

The `climate` field of `destinations.json` (warm / mild / cold) is derived from
[WorldClim 2.1](https://www.worldclim.org/) bioclimatic variable 1 (annual mean
temperature, 1970–2000, 10-minute resolution; Fick, S.E. and R.J. Hijmans, 2017,
*WorldClim 2: new 1-km spatial resolution climate surfaces for global land areas*,
International Journal of Climatology 37(12): 4302–4315), licensed under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). The data
was sampled at each destination and classified.

Suggested app credit line: *"Climate data: WorldClim 2.1 (worldclim.org), CC BY 4.0."*

## Natural Earth: public domain

`countries.json`, `countries.geojson`, `regions.json`, `regions.geojson`,
`geo_grid.npz`, the `admin1_id` links in `gazetteer.json` and `destinations.json`, and the
`coast_km` / `med_coast_km` distances in `destinations.json` are derived from
[Natural Earth](https://www.naturalearthdata.com/) (admin-0 countries, admin-1
states/provinces, land, 1:10m coastline, 1:10m marine areas). Natural Earth is in the public domain, so no attribution is
required. A credit is still appreciated: *"Made with Natural Earth."*

## Borders / point of view

- Admin-0 borders use Natural Earth's **Turkey point-of-view** variant
  (`ne_10m_admin_0_countries_tur`). Natural Earth publishes POV variants only at
  1:10m, so the 1:10m file is used and simplified for the UI. The spec asked for 1:50m,
  but there is no 1:50m TUR POV file.
- Cyprus: this POV shows **Northern Cyprus** as a separate country. Natural Earth
  gives it no ISO code, so it carries the provisional user-assigned code `XN` / `XNC`.
  The UK Sovereign Base Areas (Akrotiri, Dhekelia) and a few indeterminate areas have
  no code and are left out. See `build_geo_index.log`.
- Admin-1 regions come from the default-POV 1:10m file. Each region's country is the
  POV admin-0 country that contains it: Crimea and Sevastopol are assigned to UA, and
  Jammu and Kashmir and Ladakh follow the POV border (PK). The region ids stay
  Natural Earth's `adm1_code`.
- These choices are provisional. Radul makes the final call.
