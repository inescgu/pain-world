import requests, pathlib, zipfile
import rasterio
import rasterio.enums
import numpy as np
import pandas as pd
from rasterio.transform import xy
import gc
import tempfile

# ── Config ────────────────────────────────────────────────────────────────────
YEAR        = 2021
PARQUET_DIR = pathlib.Path("worldcover_parquet")
PARQUET_DIR.mkdir(exist_ok=True)

LANDCOVER_CLASSES = {
    10:  "trees",
    20:  "shrubland",
    30:  "grassland",
    40:  "cropland",
    50:  "built_up",
    60:  "bare_sparse",
    70:  "snow_ice",
    80:  "open_water",
    90:  "herbaceous_wetland",
    95:  "mangroves",
    100: "moss_lichen",
}

# ── Tile discovery ────────────────────────────────────────────────────────────
def get_actual_tile_list():
    api_url = "https://zenodo.org/api/records/7254221"
    r = requests.get(api_url, timeout=15)
    r.raise_for_status()
    data = r.json()
    tiles = []
    for f in data.get("files", []):
        name = f["key"]
        if name.endswith(".zip") and "macrotile_" in name:
            tile_name = name.replace(".zip", "").split("macrotile_")[-1]
            tiles.append({
                "name":    tile_name,
                "size_mb": f["size"] / 1e6,
                "url":     f["links"]["self"],
            })
    tiles.sort(key=lambda x: x["size_mb"])
    return tiles

# ── Core functions ────────────────────────────────────────────────────────────
def tif_to_dataframe(tif_path_or_bytes, name=""):
    """Works with a file path or a BytesIO object"""
    try:
        with rasterio.open(tif_path_or_bytes) as src:
            height, width = src.height, src.width
            nodata        = src.nodata
            scale         = 100
            new_h         = max(height // scale, 1)
            new_w         = max(width  // scale, 1)
            data = src.read(
                1,
                out_shape=(new_h, new_w),
                resampling=rasterio.enums.Resampling.mode,
            ).astype("uint8")
            new_transform = src.transform * src.transform.scale(
                width / new_w, height / new_h
            )
        if nodata is not None:
            data[data == int(nodata)] = 0
        mask = np.isin(data, list(LANDCOVER_CLASSES.keys()))
        if mask.sum() == 0:
            return None
        rows, cols = np.where(mask)
        lons, lats = xy(new_transform, rows, cols)
        print(f"    {name}: {new_w}x{new_h} -> {mask.sum():,} valid pixels", flush=True)
        return pd.DataFrame({
            "lat":             np.array(lats, dtype="float32"),
            "lon":             np.array(lons, dtype="float32"),
            "landcover_class": data[rows, cols].astype("uint8"),
        })
    except Exception as e:
        print(f"    [ERR] {name}: {e}", flush=True)
        return None


def process_tile_streaming(tile):
    """
    Download zip in chunks to a temp file, extract each tif one at a time,
    process it, then delete. Peak disk = size of one tif (~2-4 GB max).
    """
    tile_name = tile["name"]
    url       = tile["url"]
    size_gb   = tile["size_mb"] / 1000
    print(f"\n  Streaming {tile_name} ({size_gb:.1f} GB)...", flush=True)

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = pathlib.Path(tmp.name)

    try:
        # ── Download zip ──────────────────────────────────────────────────
        r = requests.get(url, stream=True, timeout=600)
        r.raise_for_status()
        total      = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=4 << 20):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    print(f"\r    {downloaded/1e9:.2f}/{total/1e9:.2f} GB "
                          f"({downloaded/total*100:.0f}%)", end="", flush=True)
        print()

        # ── Extract and process tifs one at a time ────────────────────────
        tile_dfs = []
        with zipfile.ZipFile(tmp_path, "r") as z:
            tif_names = sorted(n for n in z.namelist() if n.endswith("_Map.tif"))
            print(f"  Found {len(tif_names)} sub-tiles in zip", flush=True)
            for tif_name in tif_names:
                with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as ttif:
                    tif_tmp = pathlib.Path(ttif.name)
                try:
                    data_bytes = z.read(tif_name)
                    tif_tmp.write_bytes(data_bytes)
                    del data_bytes
                    gc.collect()
                    df = tif_to_dataframe(tif_tmp, name=tif_name)
                    if df is not None:
                        tile_dfs.append(df)
                finally:
                    tif_tmp.unlink(missing_ok=True)
                    gc.collect()

        return tile_dfs

    except Exception as e:
        print(f"  [ERR] {tile_name}: {e}", flush=True)
        return []
    finally:
        tmp_path.unlink(missing_ok=True)
        print(f"  [DELETED] temp zip for {tile_name}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ALL_TILES = get_actual_tile_list()
    print(f"Tiles found (sorted by size):")
    for t in ALL_TILES:
        print(f"  {t['name']:12s}  {t['size_mb']/1000:.1f} GB")

    failed_tiles = []
    processed    = 0

    for tile in ALL_TILES:
        tile_name    = tile["name"]
        parquet_path = PARQUET_DIR / f"worldcover_{tile_name}_{YEAR}.parquet"

        if parquet_path.exists():
            print(f"[SKIP] {tile_name} already done "
                  f"({parquet_path.stat().st_size/1e6:.0f} MB)", flush=True)
            processed += 1
            continue

        print(f"\n{'='*60}")
        print(f"[TILE] {tile_name}  ({tile['size_mb']/1000:.1f} GB)")
        print(f"{'='*60}", flush=True)

        tile_dfs = process_tile_streaming(tile)

        if not tile_dfs:
            failed_tiles.append((tile_name, "no_data"))
            continue

        combined_tile = pd.concat(tile_dfs, ignore_index=True)
        combined_tile["landcover_label"] = combined_tile["landcover_class"].map(LANDCOVER_CLASSES)
        combined_tile.to_parquet(parquet_path, index=False)
        print(f"  [SAVED] {tile_name} -> {len(combined_tile):,} rows "
              f"({parquet_path.stat().st_size/1e6:.1f} MB)", flush=True)

        del tile_dfs, combined_tile
        gc.collect()
        processed += 1

    # ── Combine all parquet files ─────────────────────────────────────────
    print("\n\nCombining all tiles...", flush=True)
    parquet_files = sorted(PARQUET_DIR.glob(f"worldcover_*_{YEAR}.parquet"))

    if not parquet_files:
        print("ERROR: No parquet files found.")
    else:
        combined = pd.concat(
            [pd.read_parquet(f) for f in parquet_files],
            ignore_index=True
        )
        combined["landcover_label"] = combined["landcover_class"].map(LANDCOVER_CLASSES)
        print(f"Total rows: {len(combined):,}")
        print(combined["landcover_label"].value_counts().to_string())

        out_csv = pathlib.Path("worldcover_2021_global_1km.csv")
        combined.to_csv(out_csv, index=False)
        print(f"\n[DONE] -> {out_csv}  ({out_csv.stat().st_size/1e6:.0f} MB)", flush=True)

    if failed_tiles:
        print(f"\nFailed tiles: {failed_tiles}")


if __name__ == "__main__":
    main()