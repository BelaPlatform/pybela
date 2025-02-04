# Setup for on-device inference

## Bela setup

You will need to flash the Bela experimental image `v0.5.0alpha2` which can be downloaded [here](https://github.com/BelaPlatform/bela-image-builder/releases/tag/v0.5.0alpha2). You can follow [these instructions](https://learn.bela.io/using-bela/bela-techniques/managing-your-sd-card/#flash-an-sd-card-using-balena-etcher) to flash the image onto your Bela's microSD card.

## Pull the cross-compiler Docker image

If you haven't got docker installed on your machine yet, you can follow the instructions [here](https://docs.docker.com/engine/install/). Once you have docker installed, start it (open the Docker app). There is no need to create an account to follow this tutorial.

Pull the docker image:

```bash
docker pull pelinski/xc-bela-container:v0.1.1
```

This will pull the dockerised cross-compiler. You can start the container by running:
(this will create the container for the first time. If you have created the container already, you can enter the container back by running `docker start -ia bela-container`)
If you are using a windows machine, replace `BBB_HOSTNAME=192.168.7.2` for `BBB_HOSTNAME=192.168.6.2`.

```bash
docker create -it --name bela-container -e BBB_HOSTNAME=192.168.7.2 pelinski/xc-bela-container:v1.1.0
```

We will need to copy some scripts to the container. Run the following commands:

```bash
docker cp container-scripts bela-container:/sysroot/root/
```

Now you can enter the container by running:

```bash
docker start -ia bela-container
```

You will need to copy a couple of libraries to Bela and update its core code. If your Bela has a rev C cape you will also need to update the Bela cape firmware. You can do this by running the following commands inside the container:

```bash
#in docker container
sh container-scripts/download-torch.sh
sh container-scripts/copy-libs-to-bela.sh
sh container-scripts/setup-bela-dev.sh # only run if you haven't set up your Bela dev branch yet
sh container-scripts/setup-bela-revC.sh # only if you have a rev C cape
```
