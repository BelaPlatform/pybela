# testing

pyBela has been tested with [Bela](https://github.com/BelaPlatform/Bela) at `dev` branch commit `69cdf75a` and [watcher](https://github.com/BelaPlatform/watcher) at `main` commit `903573a`.

The watcher code is already included in `bela-test`. You can update your Bela API code following [these instructions](readme.md).

To run the tests, copy the `bela-test` code into your Bela, compile and run it:

```bash
scp -r bela-test root@bela.local:Bela/projects/
ssh root@bela.local "make -C Bela stop Bela PROJECT=bela-test run"
```

Once the `bela-test` project is running on Bela, you can run the python tests by running:

```bash
pipenv run python test.py
```
