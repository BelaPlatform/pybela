# pybela

pybela allows interfacing with [Bela](https://bela.io/), the embedded audio platform, using Python. pybela provides a convenient way to stream, log, monitor sensor data from Bela to python. It also allows you to send buffers of data from python to Bela or control the value of variables in your Bela code from python.

Below, you can find instructions to install pybela. You can find code examples at `tutorials/` and `test/`. 

pybela was developed with a machine learning use case in mind. For a complete pipeline including data acquisition, processing, model training, and deployment (including rapid cross-compilation) check the [pybela-pytorch-xc-tutorial](https://github.com/pelinski/pybela-pytorch-xc-tutorial).

## [Installation and set up](#installation)
You will need to (1) install the python package in your laptop,  (2) set the Bela branch to `dev` and (3) add the watcher library to your Bela project.

### 1. Installing the python package

#### Option A:

You can install this library using `pip` (replace `pip` with `pipenv` if you are using a pipenv environment):

```python
pip install pybela
```

#### Option B:

You can also download the built package from the releases section and run (replace `pip` with `pipenv` if you are using a pipenv environment):

```bash
pip install pybela-<version>.tar.gz
```

#### Option C:

You can also install this library using [pipenv](https://pipenv.pypa.io/en/latest/installation/) by cloning this repository and running:

```bash
git clone  --recurse-submodules https://github.com/BelaPlatform/pybela
cd pybela
pipenv install
```

### 2. Set the Bela branch to `dev`

In order to use pybela, you will need to use the `dev` branch of the Bela code.

#### Option A:

If your Bela is connected to internet, you can ssh into your Bela (`ssh root@bela.local`) and change the branch:

```bash
# in Bela
cd Bela
git checkout dev
git pull
```

#### Option B:

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
```

You can check the commit hash by running `git rev-parse --short HEAD` either on Bela or your laptop.

### 3. Add the watcher library to your project

For pybela to be able to communicate with your Bela device, you will need to add the watcher library to your Bela project. To do so, you will need to add the files `Watcher.h` and `Watcher.cpp` to your Bela project. You can do this by copying the files from the `watcher` repository into your Bela project. To do so, you can run:

```bash
scp watcher/Watcher.h watcher/Watcher.cpp root@bela.local:Bela/projects/your-project/
```

## Getting started

### Modes of operation

pybela has three different modes of operation:

- **Streaming**: continuously send data from Bela to python (**NEW: or vice versa!** check the [tutorial](tutorials/notebooks/2_Streamer-python-to-Bela.ipynb)).
- **Logging**: log data in a file in Bela and then retrieve it in python.
- **Monitoring**: monitor the value of variables in the Bela code from python.
- **Controlling**: control the value of variables in the Bela code from python.

You can check the **tutorials** at tutorials/` for more detailed information and usage of each of the modes. You can also check `test/test.py` for a quick overview of the library. 

### Running the examples

The quickest way to get started is to start a jupyter notebook server and run the examples. If you haven't done it yet, install the python package as explained in the [installation section](#installation). If you don't have the `jupyter notebook` package installed, you can installed by running (replace `pip` with `pipenv` if you are using a pipenv environment):

```bash
pip install notebook
```

Once installed, start a jupyter notebook server by running:

```bash
jupyter notebook # or `pipenv run jupyter notebook` if you are using a pipenv environment
```

This should open a window in your browser from which you can look for the `tutorials/notebooks` folder and open the examples.

### Basic usage

pybela allows you to access variables defined in your Bela code from python. To do so, you need to define the variables you want to access in your Bela code using the `Watcher` library.

#### Bela side

For example, if you want to access the variable `myvar` from python, you need to define the variable in your Bela code as follows:

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

Once the variable is defined "in the watcher", you can stream, log and monitor its value from python. For example, to stream the value of `myvar` from python, you can do:

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

## Testing

This library has been tested with Bela at `dev` branch commit `69cdf75a` and watcher at `main` commit `903573a`.

To run pybela's tests first copy the `bela-test` code into your Bela, compile and run it:

```bash
rsync -rvL  test/bela-test root@bela.local:Bela/projects/
ssh root@bela.local "make -C Bela stop Bela PROJECT=bela-test run"
```

you can run the python tests by running:

```bash
python test/test.py # or `pipenv run python test/test.py` if you are using a pipenv environment
```

## Building

You can build pybela using pipenv:

```bash
pipenv install -d # installs all dependencies including dev dependencies
pipenv lock && pipenv sync # updates packages hashes
pipenv run python -m build --sdist # builds the .tar.gz file
```

## To do and known issues

- [ ] **Issue:** Monitor and streamer/controller can't be used simultaneously –  This is due to both monitor and streamer both using the same websocket connection and message format. This could be fixed by having a different message format for the monitor and the streamer (e.g., adding a header to the message)
- [ ] **Issue:** The plotting routine does not work when variables are updated at different rates.
- [ ] **Issue**: The plotting routine does not work for the monitor (it only works for the streamer)
- [ ] **Code refactor:** There are two routines for generating filenames (for Streamer and for Logger). This should be unified.
- [ ] **Possible feature:** Flexible backend buffer size for streaming: if the assign rate of variables is too slow, the buffers might not be filled and hence not sent (since the data flushed is not collected in the frontend), and there will be long delays between the variable assign and the data being sent to the frontend.
- [ ] **Issue:** Flushed buffers are not collected after `stop_streaming` in the frontend.
- [ ] **Bug:** `OSError: [Errno 12] Cannot allocate memory`

## License

This library is distributed under LGPL, the GNU Lesser General Public License (LGPL 3.0), available [here](https://www.gnu.org/licenses/lgpl-3.0.en.html).
