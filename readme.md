# pybela

pybela allows interfacing with [Bela](https://bela.io/), the embedded audio platform, using python. It offers a convenient way to stream data between Bela and python, in both directions. In addition to data streaming, pybela supports data logging, as well as variable monitoring and control functionalities.

Below, you can find instructions to install pybela. You can find code examples at `tutorials/` and `test/`. The docs are available at [https://belaplatform.github.io/pybela/](https://belaplatform.github.io/pybela/).

pybela was developed with a machine learning use-case in mind. For a complete pipeline including data acquisition, processing, model training, and deployment (including rapid cross-compilation) check the [pybela-pytorch-xc-tutorial](https://github.com/pelinski/pybela-pytorch-xc-tutorial). You can also check out the [deep-learning-for-bela](https://github.com/pelinski/deep-learning-for-bela) resource list.

## Installation and set up

You will need to (1) install the python package in your laptop, (2) set the Bela branch to `dev` and (3) add the watcher library to your Bela project.

### 1. Installing the python package

You can install this library using `pip`:

```python
pip install pybela
```

### 2. Set the Bela branch to `dev`

`pybela` is relies on the `watcher` library, which currently only works with the Bela `dev` branch. To set your Bela to the `dev` branch, you can follow the instructions below.

**Note:** if you just flashed the Bela image, the date and time on the Bela board might be wrong, and the Bela libraries might not build correctly after changing the Bela branch. To set the correct date, you can either run (in the host)

```bash
ssh root@bela.local "date -s \"`date '+%Y%m%d %T %z'`\""
```

or just open the IDE in your browser (type `bela.local` in the address bar).

#### Option A: Bela connected to internet

If your Bela is connected to internet, you can ssh into your Bela (`ssh root@bela.local`) and change the branch:

```bash
# in Bela
cd Bela
git checkout dev
make -f Makefile.libraries cleanall && make coreclean
```

#### Option B: Bela not connected to internet

If your Bela is not connected to internet, you can change the branch by cloning the Bela repository into your laptop and then pushing the `dev` branch to your Bela.
To do that, first clone the Bela repository into your laptop:

```bash
# in laptop
git clone  --recurse-submodules https://github.com/belaPlatform/bela
cd Bela
```

Then add your Bela as a remote and push the `dev` branch to your Bela:

```bash
# in laptop
git remote add board root@bela.local:Bela/
git checkout dev
git push -f board dev:tmp
```

Then ssh into your Bela (`ssh root@bela.local`) and change the branch:

```bash
# in Bela
cd Bela
git checkout tmp
make -f Makefile.libraries cleanall && make coreclean
```

You can check the commit hash by running `git rev-parse --short HEAD` either on Bela or your laptop.

### 3. Add the watcher library to your project

For pybela to be able to communicate with your Bela device, you will need to add the watcher library to your Bela project. To do so, you will need to add the files `Watcher.h` and `Watcher.cpp` to your Bela project. You can do this by copying the files from the `watcher` repository into your Bela project.

First you need to clone this repository, **don't forget to add the `--recurse-submodules` flag to the `git` command** to populate the `watcher/` folder:

```bash
# in laptop
git clone --recurse-submodules https://github.com/BelaPlatform/pybela.git
```

Then you can copy the files to your Bela project:

```bash
# in laptop
cd pybela/
scp watcher/Watcher.h watcher/Watcher.cpp root@bela.local:Bela/projects/your-project/
```

## Getting started

### Modes of operation

pybela has three different modes of operation:

- **Streaming**: continuously send data from Bela to python (**NEW: and from python to Bela!** check the [tutorial](tutorials/notebooks/3_Streamer-python-to-Bela.ipynb)).
- **Logging**: log data in a file in Bela and then retrieve it in python.
- **Monitoring**: monitor the value of variables in the Bela code from python.
- **Controlling**: control the value of variables in the Bela code from python.

You can check the **tutorials** at `tutorials/`for more detailed information and usage of each of the modes. You can also check`test/test.py` for a quick overview of the library.

### Running the tutorials

The quickest way to get started is to start a jupyter notebook server and run the tutorials. If you haven't done it yet, install the python package as explained in the Installation section. If you don't have the `jupyter notebook` package installed, you can install it by running:

```bash
pip install notebook
```

Once installed, start a jupyter notebook server by running:

```bash
jupyter notebook
```

This should open a window in your browser from which you can look for the `tutorials/notebooks` folder and open the examples.

### Basic usage

pybela allows you to access variables defined in your Bela code from python. To do so, you need to define the variables you want to access in your Bela code using the `Watcher` library.

#### Bela side

For example, if you want to access the variable `myvar` from python, you need to declare the variable in your Bela with the Watcher template:

```cpp
#include <Watcher.h>
Watcher<float> myvar("myvar");
```

You will also need to add the following lines to your `setup` loop:

```cpp
bool setup(BelaContext *context, void *userData)
{
	Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
	Bela_getDefaultWatcherManager()->setup(context->audioSampleRate);
    // your code here...
}
```

You will also need to add the following lines to your render loop:

```cpp
void render(BelaContext *context, void *userData)
{
	for(unsigned int n = 0; n < context->audioFrames; n++) {
		uint64_t frames = context->audioFramesElapsed + n;
		Bela_getDefaultWatcherManager()->tick(frames);
        // your code here...
    }
}
```

you can see an example [here](./test/bela-test/render.cpp).

#### Python side

Once the variable is declared with the Watcher template, you can stream, log, monitor and control its value from python. For example, to stream the value of `myvar` from python, you can do:

```python
from pybela import Streamer
streamer = Streamer()
streamer.connect()
streamer.start_streaming("myvar")
```

to terminate the streaming, you can run:

```python
streamer.stop_streaming()
```

## Example projects

- [pybela-drumsynth](https://github.com/jorshi/pybela-drumsynth): Audio-driven drum synthesis. This project takes audio from a microphone to control a drum synthesiser using onset detection and audio feature extraction. It uses pybela to capture an audio dataset and runs a torch model on Bela.
- [faab-hyperparams](https://github.com/pelinski/faab-hyperparams/): Project that explores sonification of latent spaces of a Transformer Autoencoder model. This project uses pybela to capture training data, and to stream data to the laptop which runs a pytorch model. The output of the model can be sent back to Bela in real-time or sent through OSC to another device.

## Testing

_This library has been tested with Bela at `dev` branch commit `69cdf75a` and watcher at `main` commit `903573a`._

To run pybela's tests first copy the `bela-test` code into your Bela, compile and run it:

```bash
rsync -rvL  test/bela-test root@bela.local:Bela/projects/
ssh root@bela.local 'make -C /root/Bela run PROJECT=bela-test'
```

Create the python environment and activate it. Our preferred environment is `uv` but you can use your environment manager of choice and install the dependencies in `requirements.txt`.

```bash
uv venv
source .venv/bin/activate
```

you can run the python tests by running:

```bash
uv run python test/test.py
```

## Building

You can build pybela using `uv`:

```bash
uv build
```

To test the build, connect your Bela to the computer. The following script will test the packaged build by running the `twine` tests, creating a new temporal virtual environment, installing the library from the dist files, and running the pybela test routine. This will take a few minutes.

```bash
sh dev/test-dist.sh
```

You can also test the docs with:

```bash
sh dev/test-docs.sh
```

## To do and known issues

- [ ] **Fix**: logger with automatic transfer too slow for large datasets
- [ ] **Issue:** Monitor and streamer/controller can't be used simultaneously –  This is due to both monitor and streamer both using the same websocket connection and message format. This could be fixed by having a different message format for the monitor and the streamer (e.g., adding a header to the message)
- [ ] **Issue:** The plotting routine does not work when variables are updated at different rates.
- [ ] **Issue**: The plotting routine does not work for the monitor (it only works for the streamer)
- [ ] **Possible feature:** Flexible backend buffer size for streaming: if the assign rate of variables is too slow, the buffers might not be filled and hence not sent (since the data flushed is not collected in the frontend), and there will be long delays between the variable assign and the data being sent to the frontend.
- [ ] **Issue:** Flushed buffers are not collected after `stop_streaming` in the frontend.

## License

This library is distributed under LGPL, the GNU Lesser General Public License (LGPL 3.0), available [here](https://www.gnu.org/licenses/lgpl-3.0.en.html).
