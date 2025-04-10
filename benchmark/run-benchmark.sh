export NUM_AUX_VARIABLES=10
export NUM_OSCS=40
export TIME=30
export TRANSPORT_MODE="USB"
export VERBOSE=0

printf ">>Running benchmark with the following parameters:"
printf "\nNUM_AUX_VARIABLES: $NUM_AUX_VARIABLES"
printf "\nNUM_OSCS: $NUM_OSCS"
printf "\nTIME: $TIME"
printf "\nTRANSPORT_MODE: $TRANSPORT_MODE"
printf "\nVERBOSE: $VERBOSE"

printf "\n>> Passing parameters to config.h file..."
# rm -f benchmark/bela2python2bela-benchmark/config.h
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

printf "\n\n>> Run the benchmark project in Bela\n"
ssh root@bela.local 'make -C /root/Bela run PROJECT=bela2python2bela-benchmark'  &

printf "\n\n>>Waiting for Bela to start...\n"
sleep 5

printf "\n\n>>Running python script...\n"
uv run python benchmark/bela2python2bela-benchmark.py --num_aux_vars $NUM_AUX_VARIABLES --num_oscs $NUM_OSCS --time $TIME --transport_mode $TRANSPORT_MODE

printf "\n\n>>Stop Bela project\n"
ssh root@bela.local 'make -C /root/Bela PROJECT=bela2python2bela-benchmark stop'