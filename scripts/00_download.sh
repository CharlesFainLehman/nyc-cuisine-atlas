#!/usr/bin/env bash
# Download raw inputs: Wayback Machine snapshots of the DOHMH inspection CSV, the current
# dataset, and borough boundaries. ~1.8 GB total; not committed to the repo.
set -euo pipefail
cd "$(dirname "$0")/../data"
mkdir -p wayback
SNAPSHOTS="20150908031922 20161210134227 20170426215535 20201106020601 20210529185923
20220626053405 20230810232010 20231117063638 20240928031215 20250502071901 20250913150157
20260121205029 20260403010027"
for ts in $SNAPSHOTS; do
  [ -s "wayback/$ts.csv" ] && continue
  curl -sL --retry 3 --compressed -o "wayback/$ts.csv" \
    "https://web.archive.org/web/${ts}id_/https://data.cityofnewyork.us/api/views/43nn-pn8j/rows.csv?accessType=DOWNLOAD"
  # some captures are stored gzipped
  if [ "$(head -c 2 "wayback/$ts.csv" | xxd -p)" = "1f8b" ]; then
    mv "wayback/$ts.csv" "wayback/$ts.csv.gz" && gunzip -f "wayback/$ts.csv.gz"
  fi
  echo "wayback/$ts.csv"
done
curl -s -o raw_inspections.csv 'https://data.cityofnewyork.us/resource/43nn-pn8j.csv?$select=camis,dba,boro,building,street,zipcode,cuisine_description,inspection_date,inspection_type,latitude,longitude,nta&$limit=2000000'
curl -s -o boroughs.geojson 'https://data.cityofnewyork.us/resource/gthc-hcne.geojson'
curl -s -o nta2020.geojson 'https://data.cityofnewyork.us/resource/9nt8-h7nd.geojson?$limit=1000'
