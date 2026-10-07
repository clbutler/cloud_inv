# cloudflip

**Will you stand above a sea of cloud at sunrise?** cloudflip forecasts the chance of a cloud inversion at each of Scotland's 282 Munros, for every morning of the coming week.

**Live site: [yourcloudflip.netlify.app](https://yourcloudflip.netlify.app)**

[![Nightly forecast](https://github.com/clbutler/cloud_inv/actions/workflows/nightly.yml/badge.svg)](https://github.com/clbutler/cloud_inv/actions/workflows/nightly.yml)

[![cloudflip: a 7-day strip, a map of all 282 Munros and the four checks for one hill](docs/screenshot.png)](https://yourcloudflip.netlify.app)

## What is a cloud inversion?

Normally the air gets colder with height. In a temperature inversion, a layer of warmer air sits above colder air. That warm "lid" traps cold, damp air in the glens, so cloud and fog fill the valleys while the summits stay clear. From the top of a Munro, the result is a sea of cloud below, often lit by the rising sun.

Scotland's 282 Munros, the mountains over 3,000 ft, are among the best places in the UK to see one. Inversions are hard to predict, though, and mountain forecasts are usually given per area, not per hill. cloudflip gives a verdict for every Munro, for every morning of the next seven days.

## How it works

```mermaid
flowchart LR
    A[Open-Meteo API<br/>Met Office UK 2 km model] --> B[Python pipeline<br/>fetch and score]
    B --> C[(SQLite database<br/>GitHub Release)]
    B --> D[site/data/scores.js]
    D --> E[cloudflip website<br/>Leaflet map]
    F[GitHub Actions<br/>daily, 04:00 UTC] -. runs .-> B
```

1. **Fetch.** `scripts/openmeteo_function.py` asks [Open-Meteo](https://open-meteo.com) for 7 days of hourly Met Office forecasts at every Munro. It gets surface weather, plus temperature, humidity, cloud and wind at six pressure levels from about 100 m to 1,500 m. The pressure levels are what make an inversion visible: a warmer layer above a colder one.
2. **Score.** `scripts/inversion_score_function.py` checks every hour from one hour before sunrise to three hours after, and keeps the best hour for each Munro and day.
3. **Store.** Every run is saved to a SQLite database (see [Data](#data)).
4. **Publish.** `scripts/site_export_function.py` writes the latest scores for the website, a static page in `site/` that uses Leaflet.
5. **Automate.** A [GitHub Actions workflow](.github/workflows/nightly.yml) runs the whole pipeline every day at 04:00 UTC and commits the new website data. Netlify redeploys the site from `main` whenever that commit lands.

## How the forecast is scored

Each Munro is graded on four checks. Each check scores pass, partial or fail.

| Check | Question | Pass | Partial |
|---|---|---|---|
| **Warm lid** | Is there a layer below the summit where the air gets *warmer* with height? | temperature rises with height | cools slower than 3 °C/km |
| **Cloud below** | Is there enough moisture in the glens to form cloud or fog? | cloud ≥ 50 % or humidity ≥ 95 % | humidity ≥ 87 % |
| **Clear summit** | Will the summit itself be out of the cloud? | humidity < 84 % and little cloud above | humidity < 87 % |
| **Still air** | Is it calm enough below the summit for the cloud to settle? | wind ≤ 11 km/h | wind ≤ 20 km/h |

- **Likely**: all four checks pass.
- **Possible**: all four at least partly pass.
- **Unlikely**: anything else.

The thresholds come from the Mountain Weather Information Service (MWIS) articles on inversions, humidity thresholds for cloud from Wang & Rossow (1995, *J. Appl. Meteor.*), and radiation-fog rules from the fog-forecasting literature. Forecast models often misjudge the height of an inversion and local detail, so the score is a guide, not a guarantee.

## Data

The SQLite database (`forecasts.db`) isn't stored in the repo's files. It's attached to a GitHub Release named `data`: see **Releases** in the repo sidebar, or go straight to [the release page](https://github.com/clbutler/cloud_inv/releases/tag/data). The repo's `data/` folder is separate and only holds the Munro list.

The nightly job downloads the database, adds that night's run and uploads it again. Before each upload, the version it downloaded is saved as `forecasts-prev.db`, a backup in case the upload fails.

| Table | Contents | Kept |
|---|---|---|
| `forecasts` | hourly model output, one row per run, Munro and hour | 7 days |
| `scores` | each run's verdict, the four check grades and the values behind them | forever |
| `sunrise` | sunrise time per run, Munro and day | forever |
| `munros` | name, height, location and model ground height | replaced each run |

The score history is kept so forecasts can later be checked against inversions people actually saw. To download the latest copy:

```bash
gh release download data --pattern forecasts.db --dir outputs
```

## Checking against satellite images

Work in progress, on the `satellite-validation` branch. The aim is to check the forecast against what actually happened and, later, to collect labelled images for training a model.

From above, an inversion looks like a sea of cloud filling the low ground, with the hilltops clear. [Sentinel-2](https://sentinel.esa.int/web/sentinel/missions/sentinel-2) photographs Britain every 2 to 5 days at 10 m resolution, so a script can look for that pattern.

```mermaid
flowchart LR
    A[Geograph photos<br/>'inversion', since 2017] --> B[Hand check<br/>was it an inversion?]
    B --> C[Satellite labeller<br/>Sentinel-2 + terrain]
    C --> D[Images + review page]
    D --> E[Hand check<br/>visible from space?]
    E --> F[Score the labeller]
```

1. **Sightings.** `main_sightings.py` searches [Geograph](https://www.geograph.org.uk) for photos taken in Britain since 2017 that mention an inversion or a sea of cloud. It needs no API key. Each photo was checked by hand; 226 of 326 showed an inversion.
2. **Labeller.** `satellite_function.py` reads Sentinel-2's scene classification (cloud, shadow, land, water and so on) in an 8 km box around each Munro or photo spot, at 40 m. It overlays the [Copernicus 30 m terrain model](https://planetarycomputer.microsoft.com/dataset/cop-dem-glo-30). Both come free from [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com), and only the small box is downloaded. The labeller then compares two areas:
   - **the top**: ground within 100 m of the summit height and within 1 km of it;
   - **the low ground**: more than 300 m below the summit, or halfway down to the valley floor on hills too small for that.

   It labels the pass **inversion** (10 % or less cloud on the top and at least 10 % on the low ground), **summit in cloud**, **clear**, **mixed** or **no data**. Away from the Munros, the "summit" is the highest ground within 1 km of where the photo was taken.
3. **Images and review.** `main_satellite_sightings.py` runs the labeller on each checked sighting. `main_satellite_images.py` draws the true-colour image of each pass, and `main_review_page.py` builds a local page for marking whether an inversion is visible in each one.
4. **Forecast check.** `main_satellite.py` labels every Munro on each day with saved scores and compares the labels with the forecast made before the pass.

**Results so far.** On 59 hand-checked Sentinel-2 images, the labeller found 79 % (19/24) of the visible cloud inversions, with a 3 % (1/35) false-positive rate. When it said "inversion" it was right 19 times in 20. The low-cloud threshold was chosen on the images from before 2022. On the held-out images from 2022 onwards, it found 10/10 with no false positives.

**Limits.**
- Sentinel-2 passes at about 11:30 UTC, so the labeller only sees inversions that last until then. Of 93 photo-confirmed inversion days, 53 had no pass over that spot at all.
- The numbers are small, and nearly every test image comes from a day when someone photographed an inversion. On ordinary showery days the false-positive rate may be higher.
- In winter, snow and long shadows can confuse Sentinel-2's cloud classification.

| File | What it holds |
|---|---|
| `data/inversion_sightings.csv` | Geograph sightings: date, place, nearest Munro, link, and the hand checks `checked` and `inversion` (Y/N) |
| `data/satellite_image_checks.csv` | one row per satellite pass over a sighting: the labeller's verdict and the hand check `visible` (is an inversion visible in the image: Y, N, maybe or unclear) |
| `outputs/satellite_vs_sightings.csv`, `outputs/satellite_images/` | the labeller's results, images and review page (not in git, rebuilt by the scripts) |
| `outputs/satellite.db`, `outputs/satellite_vs_scores.csv` | Munro labels for the days with saved scores, and the comparison with the forecast (not in git) |

```bash
cd scripts
python main_sightings.py            # update the sightings csv; keeps the hand checks
python main_satellite_sightings.py  # run the labeller on the checked sightings, about 2 minutes
python main_satellite_images.py     # true-colour image of each pass (--classes adds the cloud classes)
python main_review_page.py          # then open ../outputs/satellite_images/review.html
python main_satellite.py            # label the Munros and compare with the forecast (needs forecasts.db)
```

## Running it locally

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd scripts            # the scripts use paths relative to this folder
python main_munro.py  # about a minute; writes outputs/forecasts.db and site/data/scores.js
```

Then open `site/index.html` in a browser. No server or build step is needed.

## Project status

The original requirements (MoSCoW), and where they stand:

| Priority | Requirement | Status |
|---|---|---|
| Must | Inversion likelihood for any individual Munro | ✅ Done: click any Munro on the map or in the list |
| Must | Usable without running Python | ✅ Done: [hosted on Netlify](https://yourcloudflip.netlify.app), updated nightly |
| Must | Show when the data was fetched | ✅ Done: in the site footer |
| Should | Map of all Munros | ✅ Done |
| Should | Compare Munros | ✅ Done: "best bets" ranks every Munro for the chosen day |
| Should | Red/Amber/Green rating | ✅ Done, as Likely/Possible/Unlikely in sunrise colours, which are easier to read than red/green for colour-blind users |
| Could | Choose future dates | ✅ Done: 7-day strip |
| Could | Breakdown of the rating | ✅ Done: the four checks, with their values |
| Won't | Locations other than Munros | Out of scope |

## Credits and licences

Developed by Dr Chris Butler (project started January 2025).

- Forecast data: [Open-Meteo](https://open-meteo.com) (CC BY 4.0), using Met Office UKMO models. Open-Meteo's free tier is for non-commercial use.
- Munro list and locations: [The Database of British and Irish Hills](https://www.hills-database.co.uk/downloads.html) v8.0.1.
- Map: [Leaflet](https://leafletjs.com), with tiles © Esri.
- Scoring research: MWIS, Wang & Rossow (1995), and published radiation-fog forecasting rules.
- Satellite images: Copernicus Sentinel-2 data and the Copernicus DEM GLO-30 (© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA), accessed through Microsoft Planetary Computer.
- Sightings: photos on [Geograph Britain and Ireland](https://www.geograph.org.uk), © their photographers, licensed CC BY-SA 2.0. The repo stores only the date, place, title, photographer and link, not the photos.

**Safety:** cloudflip is an experimental forecast of scenery, not a safety tool. Before heading onto the hills, always check the [Mountain Weather Information Service](https://www.mwis.org.uk/forecasts/scottish), the [Met Office mountain forecast](https://www.metoffice.gov.uk/weather/specialist-forecasts/mountain) and, in winter, the [Scottish Avalanche Information Service](https://www.sais.gov.uk).
