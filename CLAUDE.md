# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Cloud Inversion RAG: predicts the likelihood of a cloud inversion at each Scottish Munro. It fetches Met Office model forecasts from the Open-Meteo API, saves them to a SQLite database, scores each Munro each morning Red/Amber/Green, and publishes the result as **cloudflip**, a static website in `site/` (developed by Dr Chris Butler). See `README.md` for background and the MoSCoW requirements. The long-term goal is to make it usable without running Python scripts (a web app with a map, per-Munro RAG, data timestamp, and date selection).

## Running

Dependencies are pinned in `requirements.txt` (Python 3.12). The virtual environment lives in `.venv/`, which git ignores. There's no packaging or build step. To recreate it: `/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`. Activate it with `source .venv/bin/activate`. The macOS system `python3` (3.9) doesn't have these packages.

All scripts use **paths relative to `scripts/`** (e.g. `../data/...`, `../outputs/...`) and import sibling modules by bare name, so run them from inside `scripts/`:

```bash
cd scripts
python main_munro.py        # full pipeline; about 6 requests to Open-Meteo, about a minute (it usually hits the per-minute limit once and waits 60 s)
pytest test_shapefile_create.py            # one test file
pytest test_shapefile_create.py::test_crs  # one test
```

Known issue: both test files are currently broken. They import modules that no longer exist (`shapefile_create`, `munro_map`) instead of `shapefile_create_function` / `munro_map_functions` (whose old `munro_map`/`munro_join` functions were replaced by `build_map`), and `test_shapefile_create.py` calls `shapefile_create()` with an extra output-path argument that the current function doesn't accept.

## Pipeline architecture (`scripts/main_munro.py`)

`main_munro.py` is the entry point and runs these steps in order:

1. **Shapefile** (`shapefile_create_function.shapefile_create`): reads `data/munrotab_v8.0.1.csv` (Database of British and Irish Hills, latin1 encoded) and keeps rows where column `2021 == 'MUN'`, which gives 282 Munros. It renames `DoBIH Number` to `munro_id`, the join key, because Munro names are **not** unique. It builds point geometries from `xcoord`/`ycoord` in **EPSG:27700** (OS National Grid) and writes `outputs/munro.shp`.
2. **Forecast** (`openmeteo_function`):
   - `munro_locations` reprojects the points to latitude/longitude.
   - `fetch_forecast` asks `api.open-meteo.com` for 7 days of hourly data from `models=ukmo_seamless` (the Met Office UK 2 km model, then the Met Office global model), 50 Munros per request. Times are in UTC. No API key is needed, but the free tier is for non-commercial use only.
     - Variables: surface temperature, dew point, humidity, low/mid/high cloud, 10 m wind and sea-level pressure, plus temperature, humidity, geopotential height, cloud cover and wind speed at 1000, 975, 950, 925, 900 and 850 hPa. Also the daily sunrise time.
     - `elevation=nan` (one per location) is deliberate. By default Open-Meteo adjusts `temperature_2m` from the model's ground height to the real ground height using a fixed 6.5 °C/km. That calculated value can never show an inversion. With `nan` you get the model's own value at its own ground height, which is saved as `model_elevation_m` (Ben Lomond: 413 m, not 974 m).
     - Pressure-level values are always the raw model output, and they're the main data for spotting an inversion: a higher level warmer than a lower one. At every Munro the 1000 hPa level (about 100 m) is below the model's ground (300–400 m). Open-Meteo still returns values for it, but they're extrapolated, so scoring ignores any level below `model_elevation_m`.
   - `save_forecast` writes `outputs/forecasts.db` (SQLite):
     - `munros` is replaced on each run: `munro_id` (primary key), `name`, `height_m`, `lat`, `lon`, `model_elevation_m`.
     - `sunrise` is appended to on each run: `run_time`, `munro_id`, `date`, `sunrise` (UTC). It's keyed by run so older runs can be re-scored and re-exported; the `munros` table is still replaced each run. Older databases, which kept only the latest run, are upgraded automatically.
     - `forecasts` is appended to on each run: one row per `run_time` × `model` × `munro_id` × `valid_time` (primary key), with one column per variable. Each run adds 47,376 rows, about 12 MB.

3. **Inversion score** (`inversion_score_function`): `score_run` scores every hour from 1 h before sunrise to 3 h after and keeps each day's best hour. `save_scores` writes the `scores` table: one row per `run_time` × `model` × `munro_id` × `date`, with the RAG, the four check grades and the values behind them. Each check is graded 2 (pass), 1 (partial) or 0 (fail):

   | Check | Pass | Partial | Basis |
   |---|---|---|---|
   | A. Lid: the most stable layer between two levels that are above the model's ground and below the summit | temperature rises with height | cools slower than 3 °C/km | physics; 3 °C/km is a judgement because the levels are about 250 m apart |
   | B. Moisture: the wettest level below the summit | cloud ≥ 50 % or RH ≥ 95 % | RH ≥ 87 % | hill-walking guides' valley RH > 95 %; fog rule RH ≥ 94 %; Wang & Rossow (1995) cloud RH 87 % |
   | C. Clear top: RH interpolated to summit height | RH < 84 % and mid+high cloud < 50 % | RH < 87 % | Wang & Rossow (1995): cloud-free below 84 % |
   | D. Wind in the layer where the cloud sea forms: the strongest of the 10 m wind and the levels above the model's ground and below the summit | ≤ 11 km/h | ≤ 20 km/h | radiation-fog rule ≤ 3 m/s (a surface wind), because wind in that layer mixes and breaks the lid |

   - Green = all four pass. Amber = all four at least partial. Red = anything else.
   - The summit wind (`summit_wind_kmh`) and sea-level pressure are saved as context but not scored. Strong wind *above* a lid doesn't break it, but it matters to walkers.
   - Why wind counts for Amber: before this rule, every Amber in the first test week (29 Sep–3 Oct 2026) had 20–70 km/h winds below the lid and only moderate pressure. Those were stable layers inside windy weather, not calm pools of cloud.
   - Sources: MWIS blogs *The wonder of inversions* and *Inversion forecasts – and how far you can trust them*; Wang & Rossow 1995 (J. Appl. Meteor.); the rule-based radiation fog paper in J. Hydrology 2021; the Fog Stability Index.
   - MWIS warns that models often get the inversion height and local detail wrong, so treat the score as a guide until step 3 checks it against what people actually see.

4. **cloudflip website data** (`site_export_function.export_site_data`): writes `site/data/scores.js` (about 330 kB) for the latest run: `window.CLOUDFLIP = {meta, munros, days}`. Each day maps munro id to its status `r` (0–2), best hour `t` (UTC), grades `g` [lid, moisture, clear top, wind] and the values behind them. It's a script rather than JSON because browsers block `fetch()` on pages opened from disk. Hill Bagging links come from the hills CSV, whose `DoBIH Number` is read as text and has to be cast to int.

## Website (`site/`)

Hand-written static site: `index.html`, `style.css` and `app.js`. It uses Leaflet 1.9.4 and Google Fonts from CDNs, and has no build step. Open `site/index.html` directly, or host the folder (Netlify, roadmap step 2).

- **Design ("dawn")**: slate-blue ink `#1f2a3a`, warm off-white `#f7f5f0`, sky `#eaf2fa`. Status colours are sunrise gold (Likely), apricot with an orange ring (Possible) and slate grey (Unlikely). Red/green was dropped: walkers read red as danger, and red/green is the commonest colour-blind pair. Status is also shown by marker size. Fonts: Outfit for headings and the wordmark, Inter for body text, with tabular numbers.
- **Layout**: a 400 px side panel and a full-height map; below 800 px the map sits on top with the panel underneath. Grid/flex children need `minmax(0,1fr)` / `min-width:0`, or the 7-day strip overflows on phones.
- **Panel**: brand and trust line, a 7-day strip (bar = best Munro's checks passed, coloured by the day's best status), a headline sentence (counts, best bet, or "closest call" with its main problem), search, and a best-bets list ranked by status, then checks passed, then grade total. Ties are broken by distance from the user once location is known, otherwise alphabetically; never by height, which made Ben Nevis look like a recommendation. The headline says how many Munros are tied ("and 12 others just as good"). Location is only requested by the "Near me" button, which then reads "Using your location" and adds distances and a blue you-are-here dot. If the browser has already granted permission (`navigator.permissions`), the location is used quietly on load, so the page never opens with a pop-up. Clicking a Munro (map or list) opens a detail view: hill picture, verdict, the four checks, this Munro's week, and Hill Bagging and MWIS links.
- **Other**: an explainer modal ("How does this work?"); the URL hash `#day=YYYY-MM-DD&munro=ID` so views can be shared; Esc closes things. The footer has the safety note (MWIS, Met Office mountain, SAIS), credits and fetch time.
- **Intro animation** (`#intro` in `index.html`, `.intro*` in `style.css`), about 2.5 s: it opens inside the logo's cloud (white fog), zooms out to the logo against a dawn gradient, the M draws itself (stroke-dashoffset) as a sun rises between the peaks, then the wordmark slides in and everything fades. It plays once per browser session (`sessionStorage` `cf-intro`), never with `prefers-reduced-motion`, and any tap or key skips it; there's a 4 s safety removal. The cloud's gold outline fades in during the zoom, because at 30× it showed as thick orange bands. Headless `--virtual-time-budget` doesn't advance CSS animations reliably, so to check frames, pause them with `document.getAnimations()` and set `currentTime`.
- **Logic mirrored from Python**: `hillPicture`, `verdict` and `checkValues` in `app.js` are the browser versions of the old folium popup code.
- **Tiles**: Esri World Topo Map. OSM blocks `file://` pages with no referrer (an "Access blocked" grid), and CARTO serves an "API KEY REQUIRED" watermark. Both still return HTTP 200, so check a tile by *looking* at it.
- **Testing layouts**: headless Chrome won't lay out narrower than 500 px. To check phone width, screenshot the page inside a 400 px `<iframe>`.
- **Competitor**: hillweather.co.uk does cloud base and inversions for the same 282 Munros from the same data. It's text and lists in an editorial serif style, with no map. cloudflip's angle is map-first, visual and focused on inversions.

## Legacy / scratch files

`mountain_weather_scrape.py` (single hard-coded Ben Lomond scrape), `clean_weatherforecast_scrape.py`, `get_mf_munronames.py` (it has a `grampions` typo) and `weather_forecast_scrape.py` (empty) are earlier prototypes.

The mountain-forecast.com pipeline modules `munro_metadata_functions.py` and `weather_scrape_function.py`, and `RAG_generation_function.py`, which scored their output, are no longer called from `main_munro.py`. They're kept for reference. `munro_map_functions.py` (the folium map, `outputs/munros.html`) was replaced by the `site/` website and is no longer called. The old outputs (`munro_data.csv`, `munro_weather.csv`, `RAG_weather.csv`) come from the last scrape, in August 2025.

## Roadmap (agreed 2026-09-27)

**Working rule:** tackle one roadmap step at a time. Agree the scope with the user before editing anything, and don't carry out several steps in one go.

**Direction:** this is a portfolio / learning project. The scope widens from "cloud inversions only" to "best Munro conditions" (sun, wind, cloud base), with inversions as the headline feature. The site will be hosted on Netlify. Money-making (ads, affiliate links) is optional and comes last.

**Known problems with the current model** (found by analysing `outputs/RAG_weather.csv`, Aug 2025 data):
- The summit was never warmer than the base: 0 of 2013 rows. The summit–base temperature gap averages about −6.7 °C/km, close to the standard 6.5 °C/km cooling with height. So mountain-forecast.com's "base" temperatures look calculated from the summit forecast rather than forecast independently. If so, the temperature criterion can never fire. Check this against winter data.
- Dew point, one of the README's three criteria, isn't used.
- `RAG rating` adds °C, a 0–3 cloud score and a 0/5 wind score with no calibration, and there are no Red/Amber/Green thresholds.
- Only 183 of 282 Munros are covered, because only 2 subranges are scraped.
- `create_datetime` never restarts the date for each Munro, so `Pull Date` runs up to 2028.

**Order of work:**
0. Fix the bugs and tests. Replace mountain-forecast.com scraping with Open-Meteo, covering all 282 Munros. **Open-Meteo part done 2026-09-27** (Met Office model, SQLite, see the pipeline section). The broken tests and the `create_datetime` bug are still to do. Before the nightly job, decide how much of each run to keep, because the full data is about 12 MB a run, roughly 4 GB a year. For example, keep only the useful hours or levels, or trim old runs.
1. Rebuild the scoring: an inversion score (temperature at different heights, dew point, wind, low cloud) plus a general "good hill day" score. Start saving each day's forecasts so they can be checked against what actually happened. **Inversion score done 2026-09-27** (see pipeline step 3); every run and its scores are saved. **cloudflip map done 2026-09-27**, then replaced the same day by the `site/` website. Still to do: the "good hill day" score.
2. Static Netlify site: a nightly GitHub Actions job runs the Python and writes a JSON file; the site shows a map, per-Munro RAG, when the data was pulled, a comparison view and date selection. **Site built 2026-09-27** (`site/`, see above). Still to do: deploy to Netlify and set up the nightly job. Possible later additions: dark mode and a Walkhighlands route link (slugs not yet mapped).
3. Validation: "I saw an inversion" reports from users, plus webcam and satellite (Sentinel/MODIS) checks.
4. A "from my town" filter based on driving time, then a chatbot that looks up the same forecast data (the portfolio showcase).
5. Optional money-making.

**Rejected ideas and why:**
- Instagram checks: the API has no location search, hashtag queries are capped, and reusing other people's photos raises rights issues.
- Running the Python pipeline on Netlify functions: the scrape takes far longer than their time limits.
- Relying on ads: the audience is small and seasonal, and ads bring cookie-consent duties.
