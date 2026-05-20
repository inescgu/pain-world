#!/usr/bin/env bash
# cleanup_climate_trace.sh
# Run from inside the data folder: bash clean.sh

set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
NC='\033[0m'

deleted=0
kept=0

trash() {
    local f="$1"
    if [[ "$DRY_RUN" == "1" ]]; then
        echo -e "${YLW}[DRY-RUN]${NC} would delete: $f"
    else
        rm -f "$f"
        echo -e "${RED}deleted:${NC} $f"
    fi
    ((deleted++)) || true
}

keep() {
    echo -e "${GRN}keeping:${NC}  $1"
    ((kept++)) || true
}

echo "========================================"
echo " Climate TRACE cleanup — $(pwd)"
echo " Dry run: $DRY_RUN"
echo "========================================"

# Use find instead of glob to avoid any expansion issues
while IFS= read -r f; do
    base="$(basename "$f")"

    # ── Always keep ───────────────────────────────────────────────────────
    if [[ "$base" == "geometries.gpkg" ]]; then
        keep "$base"; continue
    fi

    if [[ "$base" == "clean.sh" ]]; then
        keep "$base"; continue
    fi

    # ── Keep: source-level emissions (has lat/lon) ────────────────────────
    if [[ "$base" == *"_emissions_sources_v5_6_0.csv" ]]; then
        # Exception: non-broadcasting-vessels has no lat/lon in schema
        if [[ "$base" == "non-broadcasting-vessels_emissions_sources_v5_6_0.csv" ]]; then
            trash "$f"; continue
        fi
        keep "$base"; continue
    fi

    # ── Delete: country-level (no spatial data) ───────────────────────────
    if [[ "$base" == *"_country_emissions_v5_6_0.csv" ]]; then
        trash "$f"; continue
    fi

    # ── Delete: confidence files ──────────────────────────────────────────
    if [[ "$base" == *"_emissions_sources_confidence_v5_6_0.csv" ]]; then
        trash "$f"; continue
    fi

    # ── Delete: ownership files ───────────────────────────────────────────
    if [[ "$base" == *"_emissions_sources_ownership_v5_6_0.csv" ]]; then
        trash "$f"; continue
    fi

    # ── Anything else — warn ──────────────────────────────────────────────
    echo -e "${YLW}[UNKNOWN]${NC} $base — skipping, inspect manually"

done < <(find . -maxdepth 1 -type f \( -name "*.csv" -o -name "*.gpkg" -o -name "*.sh" \) | sort)

echo ""
echo "========================================"
echo " Kept:    $kept"
echo " Deleted: $deleted"
[[ "$DRY_RUN" == "1" ]] && echo " (DRY RUN — nothing actually deleted)"
echo "========================================"