#!/bin/bash
#SBATCH --job-name=worldcover
#SBATCH --output=slurm_logs/worldcover_%j.out
#SBATCH --error=slurm_logs/worldcover_%j.err
#SBATCH --time=24:00:00
#SBATCH --mem=30G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1

echo "Started at: $(date)"

# Change to your working directory
cd /lisc/home/user/gerardursin/pain-world/

# Make sure log directory exists
mkdir -p slurm_logs

# Load required modules
module load Python/3.14.4-weekly
source /lisc/data/scratch/menche/ines/general_env/bin/activate

echo "Running worldcover processing..."
python worldcover.py

echo "Finished at: $(date)"