# testing

pybela has been tested with [Bela](https://github.com/BelaPlatform/Bela) at `dev` branch commit `d5f0d6f` and [watcher](https://github.com/BelaPlatform/watcher) at `main` commit `903573a`.

The watcher code is already included in `bela-test`. You can update your Bela API code following [these instructions](readme.md).

To run the tests, copy the `bela-test` code into your Bela, add the `Watcher`` library compile and run it:

```bash
rsync -rvL  test/bela-test test/bela-test-send root@bela.local:Bela/projects/
ssh root@bela.local "make -C Bela stop Bela PROJECT=bela-test run"
```

Once the `bela-test` project is running on Bela, you can run the python tests by running:

```bash
uv run python test.py
```

You can also test the `bela-test-send` project by running:

```bash
ssh root@bela.local "make -C Bela stop Bela PROJECT=bela-test run"
```

and then running the python tests with:

```bash
uv run test-send.py
```
