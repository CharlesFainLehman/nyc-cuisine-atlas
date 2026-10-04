"""Merge archived + current DOHMH inspection snapshots into one row per restaurant (CAMIS).

Inputs:  data/wayback/*.csv (Wayback Machine copies of the Open Data export)
         data/raw_inspections.csv (current Socrata pull)
Outputs: data/inspections.parquet  (camis, date, type) — every distinct inspection seen
         data/restaurants_raw.parquet (one row per camis, attributes from the newest snapshot)
"""
import glob
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

COLS = {
    "CAMIS": "camis", "DBA": "dba", "BORO": "boro", "BUILDING": "building",
    "STREET": "street", "ZIPCODE": "zipcode", "CUISINE DESCRIPTION": "cuisine",
    "INSPECTION DATE": "date", "INSPECTION TYPE": "type",
    "Latitude": "lat", "Longitude": "lon", "NTA": "nta",
}


def load(path, snapshot):
    df = pd.read_csv(path, usecols=lambda c: c in COLS, dtype=str)
    df = df.rename(columns=COLS)
    df["snapshot"] = snapshot
    return df


frames = []
for p in sorted(glob.glob(os.path.join(D, "wayback", "*.csv"))):
    ts = os.path.basename(p)[:8]
    frames.append(load(p, pd.Timestamp(ts)))
    print("loaded", p, len(frames[-1]))

cur = pd.read_csv(os.path.join(D, "raw_inspections.csv"), dtype=str).rename(columns={
    "cuisine_description": "cuisine", "inspection_date": "date", "inspection_type": "type",
    "latitude": "lat", "longitude": "lon"})
cur["snapshot"] = pd.Timestamp("2026-10-04")
frames.append(cur)

df = pd.concat(frames, ignore_index=True)
df["camis"] = pd.to_numeric(df["camis"], errors="coerce")
df = df.dropna(subset=["camis"])
df["camis"] = df["camis"].astype("int64")
df["date"] = pd.to_datetime(df["date"].str[:10], errors="coerce", format="mixed")
df.loc[df["date"].dt.year < 2000, "date"] = pd.NaT  # 1900-01-01 = not yet inspected
for c in ("lat", "lon"):
    df[c] = pd.to_numeric(df[c], errors="coerce")
df.loc[(df["lat"] < 40) | (df["lon"] > -73) | (df["lon"] < -75), ["lat", "lon"]] = pd.NA
df["boro"] = df["boro"].str.title()

insp = df.dropna(subset=["date"])[["camis", "date", "type"]].drop_duplicates()
insp.to_parquet(os.path.join(D, "inspections.parquet"), index=False)

# Newest non-null value of each attribute per restaurant.
df = df.sort_values(["snapshot", "date"])
attrs = df.groupby("camis").agg(
    dba=("dba", "last"), boro=("boro", "last"), building=("building", "last"),
    street=("street", "last"), zipcode=("zipcode", "last"), cuisine=("cuisine", "last"),
    lat=("lat", "last"), lon=("lon", "last"), nta=("nta", "last"),
    first_snapshot=("snapshot", "min"), last_snapshot=("snapshot", "max"),
)
dates = insp.groupby("camis")["date"].agg(first_insp="min", last_insp="max")
prepermit = (insp[insp["type"].str.contains("Pre-permit", na=False)]
             .groupby("camis")["date"].min().rename("first_prepermit"))
r = attrs.join(dates).join(prepermit).reset_index()
r.to_parquet(os.path.join(D, "restaurants_raw.parquet"), index=False)
print(len(r), "restaurants;", r["lat"].isna().sum(), "without coordinates")
print(r["cuisine"].value_counts().to_string())
