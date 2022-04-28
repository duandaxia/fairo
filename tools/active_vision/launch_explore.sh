#!/bin/env bash
set -ex
# Launches data collection on the agent, using random exploration 
# ./launch_explore.sh /checkpoint/apratik/data_reexplore/test_slurm_collect 10
# ./launch_explore.sh /checkpoint/apratik/data_reexplore/test_slurm_collect_noise 10 --noise


if ! source activate /private/home/apratik/miniconda3/envs/droidlet; then
    echo "source activate not working, trying conda activate"
    source $(dirname $(dirname $(which conda)))/etc/profile.d/conda.sh || true
    conda activate /private/home/apratik/miniconda3/envs/droidlet
fi

data_dir=$1
# Base dir for all jobs
base_dir=/checkpoint/${USER}/jobs/reexplore/collect

dt=$(date '+%d-%m-%Y/%H:%M:%S');
job_dir=$base_dir/$dt
echo """"""""""""""""""""""""""""""
echo Job Directory $job_dir
mkdir -p $job_dir
echo """"""""""""""""""""""""""""""

cd /private/home/apratik/fairo/tools/active_vision

chmod +x explore.py
python explore.py --data_dir $data_dir --job_dir $job_dir --num_traj $2 $3