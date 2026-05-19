#!/usr/bin/env python3
"""
WorldPop 2020 population density downloader and extractor.

Dependencies:
    pip install requests rasterio numpy pandas tqdm
"""

import requests
import pathlib
import time
import sys
import logging
from datetime import datetime

import rasterio
import numpy as np
import pandas as pd
from rasterio.transform import xy
from tqdm import tqdm  # progress bars

# ── Configuration ──────────────────────────────────────────────────────────────

YEAR        = 2020
MAX_RETRIES = 3          # retry failed downloads this many times
RETRY_DELAY = 5          # seconds between retries
SLEEP_MS    = 0.5        # polite delay between countries
CHUNK_SIZE  = 1024 * 256 # 256 KB streaming chunks (helps with large files)
BASE_URL    = (
    "https://data.worldpop.org/GIS/Population_Density/"
    "Global_2000_2020_1km_UNadj"
)

OUTPUT_DIR  = pathlib.Path("worldpop_2020")
OUTPUT_CSV  = pathlib.Path("worldpop_2020_all_countries.csv")
LOG_FILE    = pathlib.Path("worldpop_2020.log")

ISO3_CODES = [
    "AFG","ALB","DZA","AND","AGO","ATG","ARG","ARM","AUS","AUT","AZE","BHS","BHR","BGD","BRB",
    "BLR","BEL","BLZ","BEN","BTN","BOL","BIH","BWA","BRA","BRN","BGR","BFA","BDI","CPV","KHM",
    "CMR","CAN","CAF","TCD","CHL","CHN","COL","COM","COD","COG","CRI","CIV","HRV","CUB","CYP",
    "CZE","DNK","DJI","DOM","ECU","EGY","SLV","GNQ","ERI","EST","SWZ","ETH","FJI","FIN","FRA",
    "GAB","GMB","GEO","DEU","GHA","GRC","GTM","GIN","GNB","GUY","HTI","HND","HUN","ISL","IND",
    "IDN","IRN","IRQ","IRL","ISR","ITA","JAM","JPN","JOR","KAZ","KEN","PRK","KOR","KWT","KGZ",
    "LAO","LVA","LBN","LSO","LBR","LBY","LTU","LUX","MDG","MWI","MYS","MDV","MLI","MLT","MRT",
    "MUS","MEX","MDA","MNG","MNE","MAR","MOZ","MMR","NAM","NPL","NLD","NZL","NIC","NER","NGA",
    "MKD","NOR","OMN","PAK","PAN","PNG","PRY","PER","PHL","POL","PRT","QAT","ROU","RUS","RWA",
    "WSM","STP","SAU","SEN","SRB","SLE","SGP","SVK","SVN","SLB","SOM","ZAF","SSD","ESP","LKA",
    "SDN","SUR","SWE","CHE","SYR","TWN","TJK","TZA","THA","TLS","TGO","TTO","TUN","TUR","TKM",
    "UGA","UKR","ARE","GBR","USA","URY","UZB","VUT","VEN","VNM","YEM","ZMB","ZWE"
]

# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    """
    Log to both the console and a persistent log file.
    tqdm.write() is used for console output so progress bars aren't clobbered.
    """
    logger = logging.getLogger("worldpop")
    logger.setLevel(logging.DEBUG)

    # File handler — full debug detail
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Console handler — routed through tqdm so bars stay intact
    class TqdmHandler(logging.StreamHandler):
        def emit(self, record):
            try:
                tqdm.write(self.format(record), file=sys.stderr)
            except Exception:
                self.handleError(record)

    ch = TqdmHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ── Download ───────────────────────────────────────────────────────────────────

def download_tif(
    iso3: str,
    year: int,
    output_dir: pathlib.Path,
    logger: logging.Logger,
    pbar: tqdm,
) -> pathlib.Path | None:
    """
    Download a WorldPop GeoTIFF with streaming + retry logic.
    Updates the outer progress bar description on each attempt.
    Returns the local path on success, None on permanent failure.
    """
    out_file = output_dir / f"{iso3}_pd_{year}.tif"

    if out_file.exists():
        logger.info(f"SKIP  {iso3} — already downloaded")
        pbar.set_postfix_str(f"{iso3} cached", refresh=True)
        return out_file

    url = (
        f"{BASE_URL}/{year}/{iso3}/"
        f"{iso3.lower()}_pd_{year}_1km_UNadj.tif"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        pbar.set_postfix_str(f"{iso3} downloading (attempt {attempt})", refresh=True)
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code != 200:
                    logger.warning(
                        f"FAIL  {iso3} — HTTP {r.status_code} "
                        f"(attempt {attempt}/{MAX_RETRIES})"
                    )
                    # 404 means file genuinely absent — no point retrying
                    if r.status_code == 404:
                        return None
                    time.sleep(RETRY_DELAY * attempt)
                    continue

                # Stream to disk and show a nested byte-level bar
                total = int(r.headers.get("content-length", 0)) or None
                with (
                    open(out_file, "wb") as fh,
                    tqdm(
                        total=total,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=f"  {iso3}",
                        leave=False,
                        position=1,       # sits below the country bar
                    ) as byte_bar,
                ):
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        fh.write(chunk)
                        byte_bar.update(len(chunk))

                size_mb = out_file.stat().st_size / 1e6
                logger.info(f"OK    {iso3} — {size_mb:.1f} MB → {out_file}")
                return out_file

        except requests.exceptions.RequestException as exc:
            logger.warning(
                f"ERR   {iso3} — {exc} (attempt {attempt}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    logger.error(f"GIVE UP {iso3} after {MAX_RETRIES} attempts")
    return None


# ── Extraction ─────────────────────────────────────────────────────────────────

def extract_population(
    tif_path: pathlib.Path,
    iso3: str,
    logger: logging.Logger,
    pbar: tqdm,
) -> pd.DataFrame | None:
    """
    Read a GeoTIFF band, mask nodata pixels, and return a tidy DataFrame.
    """
    pbar.set_postfix_str(f"{iso3} extracting", refresh=True)
    try:
        with rasterio.open(tif_path) as src:
            data      = src.read(1).astype("float64")
            nodata    = src.nodata
            transform = src.transform

        # Mask nodata and any stray negatives (WorldPop uses -99999)
        if nodata is not None:
            data[data == nodata] = np.nan
        data[data < 0] = np.nan

        rows, cols = np.where(~np.isnan(data))
        if rows.size == 0:
            logger.warning(f"EMPTY {iso3} — no valid pixels found")
            return None

        lons, lats = xy(transform, rows, cols)
        df = pd.DataFrame({
            "iso3":        iso3,
            "lat":         lats,
            "lon":         lons,
            "pop_density": data[rows, cols],
        })
        logger.info(f"EXTRACTED {iso3} — {len(df):,} valid pixels")
        return df

    except Exception as exc:
        logger.error(f"EXTRACT ERR {iso3} — {exc}")
        return None


# ── CSV writer (append mode to avoid memory blowup) ────────────────────────────

def append_to_csv(df: pd.DataFrame, path: pathlib.Path, write_header: bool) -> None:
    """Append a single-country DataFrame to the output CSV."""
    df.to_csv(path, mode="a", index=False, header=write_header)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    start_time = datetime.now()
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Remove stale CSV so we start fresh each run
    if OUTPUT_CSV.exists():
        OUTPUT_CSV.unlink()

    logger = setup_logging()
    logger.info(f"Starting WorldPop {YEAR} download — {len(ISO3_CODES)} countries")
    logger.info(f"Output directory : {OUTPUT_DIR.resolve()}")
    logger.info(f"Output CSV       : {OUTPUT_CSV.resolve()}")

    failed_download: list[tuple] = []
    failed_extract:  list[tuple] = []
    n_processed  = 0
    total_rows   = 0
    write_header = True   # only write CSV column names on first append

    # ── Outer progress bar: one tick per country ──
    with tqdm(
        total=len(ISO3_CODES),
        desc="Countries",
        unit="country",
        position=0,
        dynamic_ncols=True,
    ) as country_bar:

        for iso3 in ISO3_CODES:
            country_bar.set_description(f"Countries [{iso3}]")

            # 1 · Download
            tif_path = download_tif(iso3, YEAR, OUTPUT_DIR, logger, country_bar)
            if tif_path is None:
                failed_download.append(iso3)
                country_bar.update(1)
                time.sleep(SLEEP_MS)
                continue

            # 2 · Extract
            df = extract_population(tif_path, iso3, logger, country_bar)
            if df is None:
                failed_extract.append(iso3)
            else:
                append_to_csv(df, OUTPUT_CSV, write_header)
                write_header  = False
                total_rows   += len(df)
                n_processed  += 1

                # Keep live stats in the bar suffix
                country_bar.set_postfix(
                    ok=n_processed,
                    rows=f"{total_rows:,}",
                    dl_fail=len(failed_download),
                    ex_fail=len(failed_extract),
                    refresh=True,
                )

            country_bar.update(1)
            time.sleep(SLEEP_MS)

    # ── Summary ────────────────────────────────────────────────────────────────
    elapsed = datetime.now() - start_time
    summary = (
        f"\n{'='*60}\n"
        f"  Finished in            : {elapsed}\n"
        f"  Countries processed    : {n_processed}/{len(ISO3_CODES)}\n"
        f"  Total pixel rows       : {total_rows:,}\n"
        f"  Output CSV             : {OUTPUT_CSV}\n"
        f"  Log file               : {LOG_FILE}\n"
    )
    if failed_download:
        summary += f"  Download failures ({len(failed_download)}) : {failed_download}\n"
    if failed_extract:
        summary += f"  Extract failures  ({len(failed_extract)}) : {failed_extract}\n"
    summary += "="*60

    logger.info(summary)
    print(summary)


if __name__ == "__main__":
    main()