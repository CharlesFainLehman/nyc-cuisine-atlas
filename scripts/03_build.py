"""Classify restaurants into cuisines/regions, estimate open & close dates, and write web/data.json.

Open date:
  1. earliest "Pre-permit" inspection (the inspection a brand-new restaurant gets), else
  2. an estimate from the CAMIS id, which DOHMH issues roughly sequentially — calibrated
     against restaurants whose pre-permit date we do see (capped at the first inspection).
  CAMIS ids older than the calibration range are marked as open "before 2013".
Close date:
  Restaurants still in the current Open Data pull are open. Others closed between the last
  snapshot that lists them and the next one; we draw a date uniformly in that interval.
"""
import json
import os
import re

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
CURRENT = pd.Timestamp("2026-10-04")

r = pd.read_parquet(os.path.join(D, "restaurants_raw.parquet"))

# ---------- coordinates ----------
g = pd.read_csv(os.path.join(D, "geocode_cache.csv")).drop_duplicates("camis")
r = r.merge(g, on="camis", how="left")
r["lat"] = r["lat"].fillna(r["glat"])
r["lon"] = r["lon"].fillna(r["glon"])
addr = (r["building"].fillna("").str.strip() + "|" + r["street"].fillna("").str.upper()
        .str.split().str.join(" ") + "|" + r["zipcode"].fillna(""))
known = r.dropna(subset=["lat"]).assign(addr=addr).groupby("addr")[["lat", "lon"]].first()
miss = r["lat"].isna()
r.loc[miss, "lat"] = addr[miss].map(known["lat"])
r.loc[miss, "lon"] = addr[miss].map(known["lon"])

# ---------- cuisine taxonomy ----------
# region -> {cuisine: [DOHMH labels]}
TAXONOMY = {
    "East Asian": {
        "Chinese": ["Chinese", "Chinese/Japanese"],
        "Japanese": ["Japanese"],
        "Korean": ["Korean"],
        "Taiwanese & Bubble Tea": [],
        "Pan-Asian": ["Asian/Asian Fusion", "Asian"],
    },
    "Southeast Asian": {
        "Thai": ["Thai"],
        "Vietnamese": ["Vietnamese/Cambodian/Malaysia"],
        "Filipino": ["Filipino"],
        "Indonesian & Malaysian": ["Indonesian"],
        "Southeast Asian (other)": ["Southeast Asian"],
    },
    "South Asian & Himalayan": {
        "Indian": ["Indian"],
        "Pakistani": ["Pakistani"],
        "Bangladeshi": ["Bangladeshi"],
        "Afghan": ["Afghan"],
        "Himalayan (Tibetan/Nepali)": [],
    },
    "Middle East & North Africa": {
        "Middle Eastern": ["Middle Eastern"],
        "Yemeni": [],
        "Turkish": ["Turkish"],
        "Lebanese": ["Lebanese"],
        "Egyptian": ["Egyptian"],
        "Moroccan": ["Moroccan"],
        "Persian": ["Iranian"],
        "Armenian": ["Armenian"],
        "Mediterranean": ["Mediterranean"],
    },
    "Latin American": {
        "Mexican": ["Mexican", "Tex-Mex"],
        "Dominican": [],
        "Colombian": [],
        "Ecuadorian": [],
        "Central American": [],
        "Cuban & Puerto Rican": ["Chinese/Cuban"],
        "Peruvian": ["Peruvian"],
        "Brazilian": ["Brazilian"],
        "South American (other)": ["Chilean", "Chimichurri"],
        "Latin American (other)": ["Latin American", "Spanish",
                                   "Latin (Cuban, Dominican, Puerto Rican, South & Central American)"],
    },
    "Caribbean, African & Soul Food": {
        "Jamaican": [],
        "Trinidadian & Guyanese": [],
        "Haitian": ["Creole"],
        "Caribbean (other)": ["Caribbean"],
        "West African": [],
        "Ethiopian": ["Ethiopian"],
        "African (other)": ["African"],
        "Soul Food": ["Soul Food"],
    },
    "European & Central Asian": {
        "Italian": ["Italian", "Pizza/Italian"],
        "French": ["French", "New French"],
        "Spanish (Spain)": ["Tapas", "Basque"],
        "Greek": ["Greek"],
        "Portuguese": ["Portuguese"],
        "German": ["German"],
        "Irish": ["Irish"],
        "British": ["English"],
        "Scandinavian": ["Scandinavian"],
        "Russian": ["Russian"],
        "Polish": ["Polish"],
        "Ukrainian": [],
        "Georgian": [],
        "Uzbek & Central Asian": [],
        "Balkan": [],
        "Eastern European (other)": ["Eastern European", "Czech"],
    },
    "Jewish & Kosher": {"Jewish/Kosher": ["Jewish/Kosher"]},
}
LABEL2CUISINE = {lab: c for reg in TAXONOMY.values() for c, labs in reg.items() for lab in labs}
CUISINE2REGION = {c: reg for reg, cs in TAXONOMY.items() for c in cs}

LATIN = {"Latin American", "Spanish", "Mexican", "Other", "Bakery Products/Desserts", "Bakery",
         "Latin (Cuban, Dominican, Puerto Rican, South & Central American)", "Chicken",
         "Sandwiches", "Juice, Smoothies, Fruit Salads", "Coffee/Tea", "Café/Coffee/Tea",
         "CafÃ©/Coffee/Tea", "Seafood"}
CARIB = {"Caribbean", "Other", "Chicken", "Bakery Products/Desserts", "Bakery", "American",
         "Seafood", "Creole", "Juice, Smoothies, Fruit Salads"}
COFFEE = {"Coffee/Tea", "Café/Coffee/Tea", "CafÃ©/Coffee/Tea", "Juice, Smoothies, Fruit Salads",
          "Bottled Beverages", "Frozen Desserts", "Bakery Products/Desserts", "Other",
          "Asian/Asian Fusion", "Chinese", "Asian", "Desserts"}
ASIAN = {"Asian/Asian Fusion", "Asian", "Japanese", "Chinese", "Indian", "Other",
         "Coffee/Tea", "Southeast Asian", "Chinese/Japanese", "Thai"}
EURO = {"Eastern European", "Russian", "Other", "Bakery Products/Desserts", "Bakery",
        "Continental", "Mediterranean", "Middle Eastern", "Turkish", "Pizza", "Indian",
        "Pakistani", "Polish", "American"}
MIDEAST = {"Middle Eastern", "Coffee/Tea", "Café/Coffee/Tea", "CafÃ©/Coffee/Tea", "Other",
           "Bakery Products/Desserts", "Bakery", "Mediterranean", "Juice, Smoothies, Fruit Salads"}

# (cuisine, name regex, DOHMH labels the override may apply to) — first match wins.
NAME_RULES = [
    ("Yemeni", r"YEMEN|QAHWA|\bHARAZ\b|\bMOKHA\b|MOKA ?(&|AND) ?CO|\bYAFA\b|\bARWA\b|HADRAMOUT|"
               r"\bSANAA\b|\bADENI\b|KAHWA|JABAL|\bSABA\b|\bDIWAN\b", MIDEAST),
    ("Taiwanese & Bubble Tea", r"TAIWAN|TAIPEI|BOBA|BUBBLE ?TEA|GONG ?CHA|KUNG ?FU TEA|HEY ?TEA|"
               r"TIGER SUGAR|XING FU TANG|YI FANG|CHATIME|\bCOCO\b|MOLLY TEA|CHAGEE|TEAZZI|"
               r"MR\.? WISH|PRESOTEA|SHARETEA|\bTP TEA|YIFANG|MOGE TEE|CHICHA|\bVIVI\b|"
               r"TEA ?PULSE|NAYUKI|ROYALTEA|QUICKLY", COFFEE),
    ("Himalayan (Tibetan/Nepali)", r"TIBET|NEPAL|HIMALAY|\bMOMOS?\b|KATHMANDU|EVEREST|SHERPA|"
               r"LHASA|POTALA", ASIAN),
    ("Vietnamese", r"VIETNAM|\bPHO\b|BANH ?MI|SAIGON|HANOI", ASIAN | {"Sandwiches"}),
    ("Indonesian & Malaysian", r"MALAYSIA|NYONYA|KUALA|PENANG|INDONESIA|BALI", ASIAN),
    ("Uzbek & Central Asian", r"UZBEK|\bUZ\b|SAMARKAND|TASHKENT|BUKHAR|\bPLOV\b|CHAYHANA|"
               r"NAVRUZ|KAZAKH|KYRGYZ|TAJIK|NUR ?SULTAN", EURO),
    ("Georgian", r"GEORGIAN|KHACHAPURI|TBILISI|SAPERAVI|ADJARA|CHAKHULI|OMA'?S", EURO),
    ("Ukrainian", r"UKRAIN|\bKYIV\b|\bKIEV|ODESSA|VESELKA", EURO),
    ("Balkan", r"BALKAN|BOSNIA|SERBIA|ALBANIA|CEVAP|BUREK|KOSOVO|CROATIA|MACEDONIA", EURO),
    ("Dominican", r"DOMINIC|QUISQUEY|CIBAO|SANTO DOMINGO|LA ROMANA|MANGU|PUERTO PLATA|"
               r"\bBANI\b|SAN FRANCISCO DE MACORIS", LATIN),
    ("Colombian", r"COLOMBIA|\bPAISA|MEDELL|BOGOTA|BARRANQUILLA|\bCALI\b|ANTIOQU", LATIN),
    ("Ecuadorian", r"ECUADOR|GUAYAQUIL|CUENCA|QUITO|MANABI|AZOGUE|RIOBAMBA", LATIN),
    ("Central American", r"SALVADOR|PUPUS|HONDUR|GUATEMAL|CHAPIN|NICARAGU|COSTA RICA|PANAMA",
     LATIN),
    ("Cuban & Puerto Rican", r"CUBA|HABANA|HAVANA|PUERTO RIC|BORICUA|BORINQUEN|LECHONERA",
     LATIN),
    ("South American (other)", r"VENEZUEL|AREPERA|ARGENTIN|URUGUAY|BOLIVIA|CHILE\b|PARAGUAY",
     LATIN),
    ("Spanish (Spain)", r"TAPAS|ESPA[NÑ]A|IBERIC|BARCELONA|MADRID|PAELLA|SPAIN|BASQUE|"
               r"ANDALUC|GALICIA|CATALAN", {"Spanish"}),
    ("Jamaican", r"JAMAICA|YARDIE|\bJERK|KINGSTON|\bIRIE\b|MOBAY|NEGRIL|MONTEGO", CARIB),
    ("Trinidadian & Guyanese", r"TRINI|GUYAN|\bROTI\b|DOUBLES|GEORGETOWN|TOBAGO|SURINAM",
     CARIB),
    ("Haitian", r"HAITI|AYITI|PORT AU|KREYOL|\bLAKAY|PETION", CARIB),
    ("West African", r"SENEGAL|DAKAR|TERANGA|NIGERI|NAIJA|LAGOS|SUYA|GHANA|ACCRA|IVOIR|"
               r"GUINEA|MALI\b|GAMBIA|LIBERIA|TOGO|BENIN|WEST AFRICA|JOLLOF|FUFU",
     {"African", "Other", "Caribbean", "American", "Chicken"}),
]
NAME_RULES = [(c, re.compile(p), labs) for c, p, labs in NAME_RULES]
CHAINS = re.compile(r"CHIPOTLE|TACO BELL|QDOBA|MOE'?S SOUTHWEST|PANDA EXPRESS|SBARRO|"
                    r"AUNTIE ANNE|PINKBERRY|DUNKIN|STARBUCKS")


def classify(name, label):
    name = (name or "").upper()
    if CHAINS.search(name):
        return None
    for cuisine, rx, labs in NAME_RULES:
        if label in labs and rx.search(name):
            return cuisine
    return LABEL2CUISINE.get(label)


r["cuisine_group"] = [classify(n, l) for n, l in zip(r["dba"], r["cuisine"])]

# ---------- dates ----------
cal = r.dropna(subset=["first_prepermit"]).sort_values("camis")
cal_t = cal["first_prepermit"].astype("int64").to_numpy()
# Monotone smoothing: rolling median of dates over sorted CAMIS, then cumulative max.
med = pd.Series(cal_t).rolling(201, center=True, min_periods=25).median().cummax().to_numpy()
CAMIS_MIN = cal["camis"].iloc[100]
print("calibration:", len(cal), "restaurants; CAMIS from", CAMIS_MIN,
      "≈", pd.Timestamp(int(med[100])).date())


def camis_estimate(c):
    if c < CAMIS_MIN:
        return pd.NaT
    return pd.Timestamp(int(np.interp(c, cal["camis"].to_numpy(), med)))


est = r["camis"].map(camis_estimate)
r["open_date"] = r["first_prepermit"]
nopp = r["open_date"].isna()
r.loc[nopp, "open_date"] = pd.concat([est[nopp], r.loc[nopp, "first_insp"]], axis=1).min(axis=1)
# Old CAMIS with no pre-permit → existed before our window.
OLD = pd.Timestamp("2012-01-01")
r.loc[nopp & est.isna(), "open_date"] = OLD
r.loc[r["open_date"].isna(), "open_date"] = OLD

# A snapshot only lists restaurants in active status, so a restaurant that drops out closed
# between its last snapshot and the next one. Draw a date uniformly in that interval so that
# aggregate counts decline smoothly across long gaps (e.g. Apr 2017 → Nov 2020).
snaps = np.sort(r["last_snapshot"].unique())
is_open = r["last_snapshot"] >= CURRENT
last = r.loc[~is_open, "last_snapshot"]
nxt = pd.Series(snaps[np.searchsorted(snaps, last.to_numpy(), side="right")], index=last.index)
u = np.random.default_rng(0).random(len(last))
r["close_date"] = pd.NaT
r.loc[~is_open, "close_date"] = last + (nxt - last) * u
# Never inspected and gone → drop (permit never became a restaurant)
r = r[~(r["first_insp"].isna() & ~is_open)]

# ---------- export ----------
e = r.dropna(subset=["cuisine_group", "lat", "lon"]).copy()

# Neighborhood (2020 NTA) for each restaurant
from shapely import STRtree, points  # noqa: E402
from shapely.geometry import mapping, shape  # noqa: E402

with open(os.path.join(D, "nta2020.geojson")) as f:
    nta = json.load(f)["features"]
nta_geoms = [shape(ft["geometry"]) for ft in nta]
tree = STRtree(nta_geoms)
pt_idx, poly_idx = tree.query(points(e["lon"].to_numpy(), e["lat"].to_numpy()), predicate="within")
nbhd = np.full(len(e), -1)
nbhd[pt_idx] = poly_idx
# points just offshore/on piers: nearest neighborhood within ~150 m
miss = np.where(nbhd < 0)[0]
if len(miss):
    near = tree.query_nearest(points(e["lon"].to_numpy()[miss], e["lat"].to_numpy()[miss]),
                              max_distance=0.0015, return_distance=False)
    nbhd[miss[near[0]]] = near[1]
e["nbhd"] = nbhd
print("neighborhood assigned:", (nbhd >= 0).mean().round(4))
print(len(r), "restaurants total;", len(e), "ethnic with coordinates")
print(e["cuisine_group"].value_counts().to_string())

cuisines = [c for reg in TAXONOMY.values() for c in reg]
cidx = {c: i for i, c in enumerate(cuisines)}


def yfrac(t):
    return None if pd.isna(t) else round(t.year + (t.dayofyear - 1) / 365.25, 2)


rows = []
for x in e.itertuples():
    rows.append([
        round(x.lat, 5), round(x.lon, 5), cidx[x.cuisine_group],
        yfrac(x.open_date), yfrac(x.close_date) or 0,
        (x.dba or "").strip().title(),
        f"{(x.building or '').strip()} {' '.join((x.street or '').split()).title()}, {x.boro or ''}",
        int(x.nbhd),
    ])

out = {
    "generated": str(CURRENT.date()),
    "regions": [{"name": reg, "cuisines": [cidx[c] for c in cs]} for reg, cs in TAXONOMY.items()],
    "cuisines": cuisines,
    "fields": ["lat", "lon", "cuisine", "open", "close", "name", "address", "nbhd"],
    "rows": rows,
}
os.makedirs(os.path.join(ROOT, "web"), exist_ok=True)
with open(os.path.join(ROOT, "web", "data.json"), "w") as f:
    json.dump(out, f, separators=(",", ":"), ensure_ascii=False)

# Sanity table: open count per cuisine on July 1 of each year
yrs = list(range(2015, 2027))
tab = {}
for y in yrs:
    t = pd.Timestamp(f"{y}-07-01") if y < 2026 else CURRENT
    alive = (e["open_date"] <= t) & (e["close_date"].isna() | (e["close_date"] > t))
    tab[y] = e[alive]["cuisine_group"].value_counts()
print(pd.DataFrame(tab).fillna(0).astype(int).sort_values(2026, ascending=False).to_string())

# ---------- neighborhood outlines (simplified) ----------
# ntatype 0 = residential; 5-9 = parks, cemeteries, airports, islands (outlined, not labeled)
nfeats = []
for ft, geom in zip(nta, nta_geoms):
    pr = ft["properties"]
    lp = geom.representative_point() if geom.geom_type != "MultiPolygon" else max(geom.geoms, key=lambda g: g.area).representative_point()
    m = json.loads(json.dumps(mapping(geom.simplify(0.00012, preserve_topology=True))),
                   parse_float=lambda v: round(float(v), 5))
    nfeats.append({"type": "Feature", "geometry": m, "properties": {
        "name": pr["ntaname"], "boro": pr["boroname"], "label": pr["ntatype"] == "0",
        "lp": [round(lp.x, 5), round(lp.y, 5)]}})
with open(os.path.join(ROOT, "web", "neighborhoods.json"), "w") as f:
    json.dump({"type": "FeatureCollection", "features": nfeats}, f, separators=(",", ":"))

# ---------- borough outlines (simplified) ----------

with open(os.path.join(D, "boroughs.geojson")) as f:
    gj = json.load(f)
feats = []
for ft in gj["features"]:
    geom = shape(ft["geometry"]).simplify(0.0002, preserve_topology=True)
    m = json.loads(json.dumps(mapping(geom)), parse_float=lambda v: round(float(v), 5))
    feats.append({"type": "Feature", "properties": {"name": ft["properties"].get("boroname")},
                  "geometry": m})
with open(os.path.join(ROOT, "web", "boroughs.json"), "w") as f:
    json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))
