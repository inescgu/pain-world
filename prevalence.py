import pandas as pd
import numpy as np
import pathlib
import warnings
import argparse

# ── Configuration ──────────────────────────────────────────────────────────────
TARGET_CONDITIONS = [
    "Low back pain",
    "Neck pain",
    "Migraine",
    "Tension-type headache",
    "Headache disorders",
    "Rheumatoid arthritis",
    "Osteoarthritis",
    "Other musculoskeletal disorders",
]

# ── ISO3 crosswalk (IHME location_name → ISO3) ─────────────────────────────────
IHME_TO_ISO3: dict[str, str] = {
    "Afghanistan": "AFG", "Albania": "ALB", "Algeria": "DZA", "Andorra": "AND",
    "Angola": "AGO", "Antigua and Barbuda": "ATG", "Argentina": "ARG",
    "Armenia": "ARM", "Australia": "AUS", "Austria": "AUT", "Azerbaijan": "AZE",
    "Bahamas": "BHS", "Bahrain": "BHR", "Bangladesh": "BGD", "Barbados": "BRB",
    "Belarus": "BLR", "Belgium": "BEL", "Belize": "BLZ", "Benin": "BEN",
    "Bhutan": "BTN", "Bolivia": "BOL", "Bosnia and Herzegovina": "BIH",
    "Botswana": "BWA", "Brazil": "BRA", "Brunei": "BRN",
    "Brunei Darussalam": "BRN", "Bulgaria": "BGR", "Burkina Faso": "BFA",
    "Burundi": "BDI", "Cabo Verde": "CPV", "Cambodia": "KHM",
    "Cameroon": "CMR", "Canada": "CAN", "Central African Republic": "CAF",
    "Chad": "TCD", "Chile": "CHL", "China": "CHN", "Colombia": "COL",
    "Comoros": "COM", "Congo": "COG",
    "Democratic Republic of the Congo": "COD", "Costa Rica": "CRI",
    "Côte d'Ivoire": "CIV", "Croatia": "HRV", "Cuba": "CUB", "Cyprus": "CYP",
    "Czech Republic": "CZE", "Czechia": "CZE", "Denmark": "DNK",
    "Djibouti": "DJI", "Dominican Republic": "DOM", "Ecuador": "ECU",
    "Egypt": "EGY", "El Salvador": "SLV", "Equatorial Guinea": "GNQ",
    "Eritrea": "ERI", "Estonia": "EST", "Eswatini": "SWZ", "Ethiopia": "ETH",
    "Fiji": "FJI", "Finland": "FIN", "France": "FRA", "Gabon": "GAB",
    "Gambia": "GMB", "Georgia": "GEO", "Germany": "DEU", "Ghana": "GHA",
    "Greece": "GRC", "Guatemala": "GTM", "Guinea": "GIN",
    "Guinea-Bissau": "GNB", "Guyana": "GUY", "Haiti": "HTI",
    "Honduras": "HND", "Hungary": "HUN", "Iceland": "ISL", "India": "IND",
    "Indonesia": "IDN", "Iran": "IRN",
    "Iran (Islamic Republic of)": "IRN", "Iraq": "IRQ", "Ireland": "IRL",
    "Israel": "ISR", "Italy": "ITA", "Jamaica": "JAM", "Japan": "JPN",
    "Jordan": "JOR", "Kazakhstan": "KAZ", "Kenya": "KEN",
    "North Korea": "PRK", "South Korea": "KOR",
    "Democratic People's Republic of Korea": "PRK",
    "Republic of Korea": "KOR", "Kuwait": "KWT", "Kyrgyzstan": "KGZ",
    "Lao PDR": "LAO", "Laos": "LAO", "Latvia": "LVA", "Lebanon": "LBN",
    "Lesotho": "LSO", "Liberia": "LBR", "Libya": "LBY", "Lithuania": "LTU",
    "Luxembourg": "LUX", "Madagascar": "MDG", "Malawi": "MWI",
    "Malaysia": "MYS", "Maldives": "MDV", "Mali": "MLI", "Malta": "MLT",
    "Mauritania": "MRT", "Mauritius": "MUS", "Mexico": "MEX",
    "Moldova": "MDA", "Republic of Moldova": "MDA", "Mongolia": "MNG",
    "Montenegro": "MNE", "Morocco": "MAR", "Mozambique": "MOZ",
    "Myanmar": "MMR", "Namibia": "NAM", "Nepal": "NPL",
    "Netherlands": "NLD", "New Zealand": "NZL", "Nicaragua": "NIC",
    "Niger": "NER", "Nigeria": "NGA", "North Macedonia": "MKD",
    "Norway": "NOR", "Oman": "OMN", "Pakistan": "PAK", "Panama": "PAN",
    "Papua New Guinea": "PNG", "Paraguay": "PRY", "Peru": "PER",
    "Philippines": "PHL", "Poland": "POL", "Portugal": "PRT", "Qatar": "QAT",
    "Romania": "ROU", "Russia": "RUS", "Russian Federation": "RUS",
    "Rwanda": "RWA", "Samoa": "WSM", "Sao Tome and Principe": "STP",
    "Saudi Arabia": "SAU", "Senegal": "SEN", "Serbia": "SRB",
    "Sierra Leone": "SLE", "Singapore": "SGP", "Slovakia": "SVK",
    "Slovenia": "SVN", "Solomon Islands": "SLB", "Somalia": "SOM",
    "South Africa": "ZAF", "South Sudan": "SSD", "Spain": "ESP",
    "Sri Lanka": "LKA", "Sudan": "SDN", "Suriname": "SUR", "Sweden": "SWE",
    "Switzerland": "CHE", "Syria": "SYR", "Syrian Arab Republic": "SYR",
    "Taiwan": "TWN", "Taiwan (Province of China)": "TWN",
    "Tajikistan": "TJK", "Tanzania": "TZA",
    "United Republic of Tanzania": "TZA", "Thailand": "THA",
    "Timor-Leste": "TLS", "Togo": "TGO", "Trinidad and Tobago": "TTO",
    "Tunisia": "TUN", "Turkey": "TUR", "Türkiye": "TUR",
    "Turkmenistan": "TKM", "Uganda": "UGA", "Ukraine": "UKR",
    "United Arab Emirates": "ARE", "United Kingdom": "GBR",
    "United States": "USA", "United States of America": "USA",
    "Uruguay": "URY", "Uzbekistan": "UZB", "Vanuatu": "VUT",
    "Venezuela": "VEN", "Venezuela (Bolivarian Republic of)": "VEN",
    "Vietnam": "VNM", "Viet Nam": "VNM", "Yemen": "YEM",
    "Zambia": "ZMB", "Zimbabwe": "ZWE",
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load & filter IHME
# ══════════════════════════════════════════════════════════════════════════════
def load_and_filter_ihme(path: str | pathlib.Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df = df[
        (df["measure_name"] == "Prevalence")
        & (df["sex_name"]    == "Both")
        & (df["age_name"]    == "Age-standardized")
    ].copy()

    if df.empty:
        raise ValueError(
            "No rows remain after filtering. "
            "Check measure_name / sex_name / age_name values in your CSV.\n"
            f"Unique measure_name values : {pd.read_csv(path)['measure_name'].unique()}\n"
            f"Unique sex_name values     : {pd.read_csv(path)['sex_name'].unique()}\n"
            f"Unique age_name values     : {pd.read_csv(path)['age_name'].unique()}"
        )

    df["iso3"] = df["location_name"].map(IHME_TO_ISO3)
    unmatched = df[df["iso3"].isna()]["location_name"].unique()
    if len(unmatched):
        warnings.warn(f"[ISO3] No match for: {unmatched}")

    print(
        f"[IHME] {len(df):,} rows after filter "
        f"| {df['cause_name'].nunique()} causes "
        f"| {df['location_name'].nunique()} countries"
    )
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Impute missing val / upper / lower
# ══════════════════════════════════════════════════════════════════════════════
def impute(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["imputed"]        = False
    df["imputed_fields"] = ""
    GRP = ["cause_name", "metric_name", "year"]

    # val from midpoint of bounds
    m = df["val"].isna() & df["upper"].notna() & df["lower"].notna()
    df.loc[m, "val"]            = (df.loc[m, "upper"] + df.loc[m, "lower"]) / 2
    df.loc[m, "imputed"]        = True
    df.loc[m, "imputed_fields"] += "val(midpoint);"

    # bounds from val via group-median ratio
    df["_ru"] = np.where(df["val"] > 0, df["upper"] / df["val"], np.nan)
    df["_rl"] = np.where(df["val"] > 0, df["lower"] / df["val"], np.nan)
    df["_mru"] = df.groupby(GRP)["_ru"].transform("median")
    df["_mrl"] = df.groupby(GRP)["_rl"].transform("median")

    mu = df["upper"].isna() & df["val"].notna()
    df.loc[mu, "upper"]          = df.loc[mu, "val"] * df.loc[mu, "_mru"]
    df.loc[mu, "imputed"]        = True
    df.loc[mu, "imputed_fields"] += "upper(ratio);"

    ml = df["lower"].isna() & df["val"].notna()
    df.loc[ml, "lower"]          = df.loc[ml, "val"] * df.loc[ml, "_mrl"]
    df.loc[ml, "imputed"]        = True
    df.loc[ml, "imputed_fields"] += "lower(ratio);"

    # val from group median
    df["_gm"] = df.groupby(GRP)["val"].transform("median")
    mv = df["val"].isna()
    df.loc[mv, "val"]            = df.loc[mv, "_gm"]
    df.loc[mv, "imputed"]        = True
    df.loc[mv, "imputed_fields"] += "val(group_median);"

    # global fallback
    for col in ["val", "upper", "lower"]:
        mg = df[col].isna()
        if mg.any():
            df.loc[mg, col]               = df[col].median()
            df.loc[mg, "imputed"]         = True
            df.loc[mg, "imputed_fields"] += f"{col}(global_median);"

    df.drop(columns=["_ru", "_rl", "_mru", "_mrl", "_gm"], inplace=True)
    print(f"[IMPUTE] {df['imputed'].sum():,} rows imputed")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Compute national absolute prevalence counts
# ══════════════════════════════════════════════════════════════════════════════
def compute_national_absolute(
    df: pd.DataFrame,
    country_pop: pd.DataFrame,
) -> pd.DataFrame:
    df = df.merge(
        country_pop[["iso3", "total_population"]],
        on="iso3", how="left"
    )
    missing_pop = df["total_population"].isna().sum()
    if missing_pop:
        warnings.warn(
            f"[POP] {missing_pop} rows have no WorldPop match — abs values will be NaN"
        )

    def _convert(col: str) -> pd.Series:
        out = pd.Series(np.nan, index=df.index)
        n   = df["metric_name"] == "Number"
        r   = df["metric_name"] == "Rate"
        p   = df["metric_name"] == "Percent"
        out[n] = df.loc[n, col]
        out[r] = (df.loc[r, col] / 100_000) * df.loc[r, "total_population"]
        out[p] = (df.loc[p, col] / 100)     * df.loc[p, "total_population"]
        return out

    df["abs_val"]   = _convert("val")
    df["abs_upper"] = _convert("upper")
    df["abs_lower"] = _convert("lower")

    print("[NATIONAL] Absolute counts computed.")
    print(
        df.groupby("cause_name")[["abs_val"]]
        .sum().sort_values("abs_val", ascending=False)
        .to_string()
    )
    return df


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Load WorldPop pixel file & aggregate to country totals
# ══════════════════════════════════════════════════════════════════════════════
def load_worldpop(path: str | pathlib.Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    print(f"[WORLDPOP] Reading {path} …")
    pixels = pd.read_csv(path, usecols=["iso3", "lat", "lon", "pop_density"])
    pixels = pixels[pixels["pop_density"] > 0].copy()

    country_pop = (
        pixels.groupby("iso3", sort=True)["pop_density"]
        .sum()
        .reset_index()
        .rename(columns={"pop_density": "total_population"})
    )
    print(
        f"[WORLDPOP] {len(pixels):,} valid pixels | "
        f"{len(country_pop):,} countries"
    )
    return pixels, country_pop


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Distribute national burden to pixels
# ══════════════════════════════════════════════════════════════════════════════
def distribute_to_pixels(
    national: pd.DataFrame,
    pixels: pd.DataFrame,
) -> pd.DataFrame:
    nat_slim = national[[
        "iso3", "cause_name",
        "abs_val", "abs_upper", "abs_lower",
        "total_population",
        "imputed", "imputed_fields",
    ]].dropna(subset=["abs_val"]).copy()

    print("[DISTRIBUTE] Merging pixels × causes …")
    merged = pixels.merge(nat_slim, on="iso3", how="inner")

    merged["pixel_share"]          = merged["pop_density"] / merged["total_population"]
    merged["pixel_abs_prevalence"] = merged["pixel_share"] * merged["abs_val"]
    merged["pixel_abs_upper"]      = merged["pixel_share"] * merged["abs_upper"]
    merged["pixel_abs_lower"]      = merged["pixel_share"] * merged["abs_lower"]

    merged.drop(columns=["pixel_share", "total_population"], inplace=True)

    print(
        f"[DISTRIBUTE] Output: {len(merged):,} rows "
        f"({pixels['iso3'].nunique()} countries × "
        f"{nat_slim['cause_name'].nunique()} causes)"
    )
    return merged.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Master pipeline
# ══════════════════════════════════════════════════════════════════════════════
def run_pipeline(
    ihme_path:     str | pathlib.Path,
    worldpop_path: str | pathlib.Path,
    output_dir:    str | pathlib.Path = "output",
) -> dict[str, pd.DataFrame]:

    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    pixels, country_pop = load_worldpop(worldpop_path)
    ihme                = load_and_filter_ihme(ihme_path)
    ihme                = impute(ihme)
    national            = compute_national_absolute(ihme, country_pop)
    pixel_burden        = distribute_to_pixels(national, pixels)

    # Save outputs
    out_pixels   = output_dir / "prevalence_by_pixel.csv"
    out_national = output_dir / "prevalence_national.csv"
    out_imputed  = output_dir / "imputed_log.csv"

    pixel_burden.to_csv(out_pixels, index=False)

    national[[
        "location_name", "iso3", "cause_name",
        "metric_name", "val", "abs_val", "abs_upper", "abs_lower",
        "total_population", "imputed", "imputed_fields",
    ]].to_csv(out_national, index=False)

    national[national["imputed"]].to_csv(out_imputed, index=False)

    print(f"\n[DONE] Written to {output_dir}/")
    print(f"  prevalence_by_pixel.csv  : {len(pixel_burden):,} rows")
    print(f"  prevalence_national.csv  : {len(national):,} rows")
    print(f"  imputed_log.csv          : {national['imputed'].sum():,} rows")

    return {
        "pixel_burden": pixel_burden,
        "national":     national,
        "country_pop":  country_pop,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IHME × WorldPop prevalence pipeline")
    parser.add_argument("--ihme",      required=True,  help="Path to IHME CSV file")
    parser.add_argument("--worldpop",  required=True,  help="Path to WorldPop pixel CSV file")
    parser.add_argument("--output",    default="output", help="Output directory (default: output)")
    args = parser.parse_args()

    run_pipeline(
        ihme_path     = args.ihme,
        worldpop_path = args.worldpop,
        output_dir    = args.output,
    )