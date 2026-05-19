#!/bin/bash
#SBATCH --job-name=wp
#SBATCH --output=slurm_logs/wp_%j.out
#SBATCH --error=slurm_logs/wp_%j.err
#SBATCH --time=12:00:00
#SBATCH --mem=10G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --array=1

echo "Started at: $(date)"

# Change to your working directory
cd /lisc/home/user/gerardursin/pain-world/

# Load required modules
module load Python/3.14.4-weekly  
source /lisc/data/scratch/menche/ines/general_env/bin/activate

# Run the job
echo "Running download of worldpop..."
python worldpop.py
    
echo "Finished at: $(date)"