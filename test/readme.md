# testing

`test.py` expects the Bela to be connected. Tested with [Bela](https://github.com/BelaPlatform/Bela) at `dev` branch commit `69cdf75a` and [watcher](https://github.com/BelaPlatform/watcher) at `main` commit `903573a`.

The watcher code is already included in `bela-test`. You can update your Bela API code following [these instructions](https://github.com/giuliomoro/git-tutorial#bela-workflow).

To run the tests, copy the `bela-test` code into your Bela

```bash
scp -r bela-test root@bela.local:Bela/projects/
```

From the Bela IDE, compile and run the `bela-test` project. Then, from your computer, you can run the tests using:

```bash
pipenv run python test.py
```
