# testing

`test.py` expects the Bela to be connected. The Bela API code should be running this dev version `3aee7b48`. You can update your board following [these instructions](https://github.com/giuliomoro/git-tutorial#bela-workflow).

The Bela testing code depends on the `Watcher.h` library, which can be found [here](https://github.com/BelaPlatform/watcher). Clone this repo into `Bela/projects`: https://github.com/BelaPlatform/watcher, you can use the git instructions provided above. Once cloned into your Bela board, you can replace the `render.cpp` with the one provided [in this folder](render.cpp).