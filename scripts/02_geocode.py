"""Geocode restaurants that only appear in pre-2020 snapshots (which lack lat/lon)
via the US Census batch geocoder. Results cached in data/geocode_cache.csv."""
import io
import os

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
CACHE = os.path.join(D, "geocode_cache.csv")
URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

r = pd.read_parquet(os.path.join(D, "restaurants_raw.parquet"))
todo = r[r["lat"].isna() & r["building"].notna() & r["street"].notna()].copy()
done = pd.read_csv(CACHE) if os.path.exists(CACHE) else pd.DataFrame(columns=["camis", "glat", "glon"])
todo = todo[~todo["camis"].isin(done["camis"])]
print(len(todo), "to geocode")

todo["street_addr"] = (todo["building"].str.strip() + " " + todo["street"].str.split().str.join(" "))
todo["city"] = todo["boro"].replace({"Manhattan": "New York"})
todo["state"] = "NY"

out = [done]
for i in range(0, len(todo), 5000):
    chunk = todo.iloc[i:i + 5000][["camis", "street_addr", "city", "state", "zipcode"]]
    buf = chunk.to_csv(index=False, header=False)
    resp = requests.post(URL, files={"addressFile": ("a.csv", buf)},
                         data={"benchmark": "Public_AR_Current"}, timeout=900)
    res = pd.read_csv(io.StringIO(resp.text), header=None, dtype=str,
                      names=["camis", "input", "match", "exact", "matched", "coords", "tiger", "side"])
    res = res[res["match"] == "Match"].copy()
    xy = res["coords"].str.split(",", expand=True).astype(float)
    res = pd.DataFrame({"camis": res["camis"].astype("int64"), "glat": xy[1], "glon": xy[0]})
    print(f"batch {i}: {len(res)}/{len(chunk)} matched")
    out.append(res)
    pd.concat(out).to_csv(CACHE, index=False)
