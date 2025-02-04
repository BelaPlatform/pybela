# pybela-drumsynth

project originally by [@jorshi](https://github.com/jorshi)

In this project, I explore how to incorporate pybela into an existing Bela project for audio-driven drum synthesis. The main idea of that project is to use audio from a microphone to control a drum synthesizer using onset detection and audio feature extraction -- which map to synthesis parameter updates.

## Setup

Follow the instructions in [bela-setup.md](bela-setup.md) to setup your Bela and the Docker cross-compilation container.

Then, on your computer and in this current folder, install the python environment either with `pip -r requirements.txt` or with `uv`.

## Getting started

Start a Jupyter server with (or open the `drumsynth_pybela.ipynb` notebook in your favorite editor):

```bash
jupyter notebook # or `uv run jupyter notebook`
```

And open `drumsynth_pybela.ipynb` -- follow the tutorial in the notebook. You'll need to have your Bela connected at this point.

In the notebook you'll copy the drumsynth code over to Bela, log audio features from Bela to Python, train a model, and copy it over to Bela. There are also instructions on compiling inference code and running that on Bela.
