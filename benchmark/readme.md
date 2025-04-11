# bela2python2bela benchmark

_tested using Bela `dev` branch commit `63c8089a`_

To run the benchmarking routine, first connect your Bela board to your computer. Then, open a terminal in this directory and run the following command:

```bash
bash run_benchmark.sh
```

This will run the benchmark for each configuration and save the results in the `data/` directory. See `data-processing.ipynb` for the data processing code, to obtain, for each configuration, average and maximum latency, jitter, and CPU usage.
