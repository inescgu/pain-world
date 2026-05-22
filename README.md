# pain-world

processing data for the ars electronica project

1. please load worldpop data first (worldpop.sh, worldpop.py)
2. worldcover needs to download quite a bit so can take a while and be memory intensive, even with the current run
3. please use the prevalence.py and prev.sh scripts for ihme data, after worldpop is computed and make sure you have disc space (takes 75G, 12 hours and saves a file that's 90G) 
4. hdi is super straightforward 
5. climate trace requires a bunch of manual data downloading + reuploading, but runs fine as a notebook (download all the co2 data per category, and upload the csv files in each 'DATA' folder into a climatetrace folder on the repo, then run clean.sh to delete unnecessary files)

See Methods : https://docs.google.com/document/d/1qa8WMmJcrIFsm_2v8dbo-vTAX-0U3SisrYbNVgTglwQ/edit?usp=sharing
