#!/bin/bash

export NUM_AUX_VARIABLES=100
export NUM_OSCS=0
export TIME=60
export TRANSPORT_MODE="USB"
export VERBOSE=0

for NUM_AUX_VARIABLES in 1 5 10 20 50 100
do

    printf "\n\n==============================="
    printf "\n>>Running benchmark for NUM_AUX_VARIABLES=$NUM_AUX_VARIABLES"
    printf "\n===============================\n"

    printf ">>Running benchmark with the following parameters:"
    printf "\nNUM_AUX_VARIABLES: $NUM_AUX_VARIABLES"
    printf "\nNUM_OSCS: $NUM_OSCS"
    printf "\nTIME: $TIME"
    printf "\nTRANSPORT_MODE: $TRANSPORT_MODE"
    printf "\nVERBOSE: $VERBOSE"

    # avoid recompilation with
    # bash benchmark/run-benchmark.sh testing 
    if [ "$1" != "testing" ]; then 
        printf "\n>> Passing parameters to config.h file..."
        cat <<EOL > benchmark/bela2python2bela-benchmark/config.h
#ifndef CONFIG_H
#define CONFIG_H

#define NUM_AUX_VARIABLES $NUM_AUX_VARIABLES
#define NUM_OSCS $NUM_OSCS
#define VERBOSE $VERBOSE

#endif // CONFIG_H
EOL

        printf "\n\n>>Copying benchmark project files to Bela...\n"
        rsync -avL benchmark/bela2python2bela-benchmark root@bela.local:Bela/projects/

        printf "\n\n>>Compile the benchmark project on Bela...\n"
        ssh root@bela.local 'make -C /root/Bela PROJECT=bela2python2bela-benchmark' 
    fi

    printf "\n\n>> Starting the node bela-cpu.js process...\n"
    timestamp=$(date +%Y%m%d_%H%M%S)
    echo $timestamp
    cpu_logs_bela_path="/root/Bela/projects/bela2python2bela-benchmark/cpu-logs"
    root_filename=$timestamp-${TRANSPORT_MODE}-V${NUM_AUX_VARIABLES}-O${NUM_OSCS}
    cpu_logs_filename=$root_filename"_cpu-load.log"

    # kill previous instances
    ssh root@bela.local "pkill -f -SIGINT 'bela-cpu.js'" 

    # make sure logs paths exists
    ssh root@bela.local "mkdir -p ${cpu_logs_bela_path}"

    # start node process
    ssh root@bela.local "stdbuf -o0 -i0 -e0 node /root/Bela/IDE/dist/bela-cpu.js > ${cpu_logs_bela_path}/${cpu_logs_filename} 2>&1 &"  

    sleep 1 # give some time to node to start

    printf "\n\n>> Run the benchmark project in Bela\n"
    ssh root@bela.local 'make -C /root/Bela run PROJECT=bela2python2bela-benchmark'  &

    printf "\n\n>>Waiting for Bela to start...\n"
    sleep 5

    printf "\n\n>>Running python script...\n"
    uv run python benchmark/bela2python2bela-benchmark.py --rfn $root_filename --time $TIME --numAuxVars $NUM_AUX_VARIABLES

    printf "\n\n>>Stop Bela project\n"
    ssh root@bela.local 'make -C /root/Bela PROJECT=bela2python2bela-benchmark stop'

    printf "\n\n>>Stop CPU Monitoring...\n"
    ssh root@bela.local "pkill -f -SIGINT 'bela-cpu.js'" 

    sleep 2

    printf "\n\n>>Copying CPU logs from Bela...\n"
    rsync -av root@bela.local:$cpu_logs_bela_path/$cpu_logs_filename benchmark/data/$cpu_logs_filename
    # cpu-logs legend: MSW, CPU usage, audio thread CPU usage

    printf "\n\n>>Benchmark complete for NUM_AUX_VARIABLES=$NUM_AUX_VARIABLES\n"
done