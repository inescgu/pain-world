#!/bin/bash
#SBATCH --job-name=prevalence_pipeline
#SBATCH --output=slurm_logs/prevalence_%j.out
#SBATCH --error=slurm_logs/prevalence_%j.err
#SBATCH --time=12:00:00
#SBATCH --mem=40G          # pixel×cause merge can be large — adjust as needed
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1

echo "Started at: $(date)"

# ── Paths ──────────────────────────────────────────────────────────────────────
WORKDIR="/lisc/home/user/gerardursin/pain-world"
IHME_CSV="${WORKDIR}/IHME-GBD_2023_DATA.csv"       # <-- update
WORLDPOP_CSV="${WORKDIR}/worldpop_2020_all_countries.csv"   # <-- update
OUTPUT_DIR="${WORKDIR}/output"

# ── Environment ────────────────────────────────────────────────────────────────
cd "${WORKDIR}"
mkdir -p slurm_logs "${OUTPUT_DIR}"

module load Python/3.14.4-weekly
source /lisc/data/scratch/menche/ines/general_env/bin/activate

# ── Run ────────────────────────────────────────────────────────────────────────
echo "Running prevalence pipeline..."

python prevalence_pipeline.py \
    --ihme     "${IHME_CSV}"     \
    --worldpop "${WORLDPOP_CSV}" \
    --output   "${OUTPUT_DIR}"

echo "Finished at: $(date)"