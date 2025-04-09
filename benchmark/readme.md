# bela2python2bela benchmark

_tested using Bela `dev` branch commit `63c8089a`_

copy the Bela code onto Bela

```bash
rsync -av benchmark/bela2python2bela-benchmark root@bela.local:Bela/projects/
```

run the `bela2python2bela-benchmark` project in Bela from the IDE

```bash
python benchmark/bela2python2bela-benchmark.py
```

this will run the benchmark and save the cpu load logs and roundtrip latency measurements in the `benchmark/data/` folder
