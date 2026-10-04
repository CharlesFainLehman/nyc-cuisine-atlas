# NYC Cuisine Atlas

An interactive map of New York City's ethnic restaurants by cuisine, 2015–2026, rebuilt from
archived NYC Health Department restaurant inspection data.

**Live map:** https://charlesfainlehman.github.io/nyc-cuisine-atlas/

Inspired by Chris Goldammer's [Yemeni coffee shop map](https://x.com/floor_per_area/status/2106723372059238816).

## What it shows

- A year slider (2015–2026) over ~27,000 restaurants in 57 cuisines and 8 regions
- **Compare** up to three cuisines on the map, or switch to **Diversity** (distinct cuisines per ~400 m hexagon)
- A cuisine index with counts, sparklines and change since 2015
- Neighborhood outlines and names (2020 NTAs); hover anywhere for a neighborhood's cuisine mix
- Line chart of selected cuisines, and the regional mix year by year (click a region to drill in)

## Data and method

The [DOHMH inspection dataset](https://data.cityofnewyork.us/Health/DOHMH-New-York-City-Restaurant-Inspection-Results/43nn-pn8j)
only lists restaurants that are open now, with about three years of inspections. Earlier years are
rebuilt from 13 Wayback Machine copies of the dataset's CSV export (Sept 2015 – Apr 2026) plus the
current data: about 63,000 restaurants, including those that have since closed.

- **Cuisine**: the inspector's cuisine label, mapped to a taxonomy. Restaurant names refine broad
  labels (a "Coffee/Tea" shop named Qahwah House → Yemeni). Name-based cuisines are undercounts.
  American, pizza, coffee, bakery and similar labels and a few national chains are excluded.
- **Opening date**: first pre-permit inspection, else estimated from the CAMIS permit ID, which is
  issued roughly in sequence (rank correlation 0.92 with pre-permit dates).
- **Closing date**: drawn uniformly between the last snapshot that lists the restaurant and the next one.
- **Coordinates**: from the dataset; restaurants that closed before 2020 are geocoded with the
  US Census batch geocoder (93% matched).

Caveats: no snapshots exist between April 2017 and November 2020, so 2018–2020 are estimated and
short-lived restaurants from that stretch are missing. An ownership change can make an old
restaurant look new.

## Rebuild

```bash
python3 -m venv .venv && .venv/bin/pip install pandas pyarrow requests shapely
scripts/00_download.sh                       # ~1.8 GB of raw snapshots (not in the repo)
.venv/bin/python scripts/01_consolidate.py   # merge snapshots → data/*.parquet
.venv/bin/python scripts/02_geocode.py       # geocode pre-2020 rows (cached in data/geocode_cache.csv)
.venv/bin/python scripts/03_build.py         # classify, date → web/data.json
.venv/bin/python scripts/04_site.py          # wrap for GitHub Pages → docs/
python3 -m http.server 8765 -d docs          # preview
```

The consolidated `data/*.parquet` files and geocode cache are committed, so you can skip the
download and start at `03_build.py`. The cuisine taxonomy and name rules are at the top of
`scripts/03_build.py`.
