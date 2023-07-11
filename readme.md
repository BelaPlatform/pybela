# Prototypes for pyBelaAPI

- `cpp/PyBela.h`: Runtime cpp pyBelaAPI -- to be called and used inside of a Bela program
- `python/pyBela.py`: Python pyBelaAPI -- interacts with the cpp API but can also interact outside of the Bela program (i.e., non-runtime operations, like moving and creating files, running and stopping Bela programs).

### non-runtime side of the API

So there's still lacking a prototype for a **cpp library** that will listen and execute non-runtime commands coming from python (like running and stopping Bela programs) -- I am not very sure how to do this and this is probably better implemented by someone familiar with the Bela core.

Functionality:
– Triggering compilation in Bela, passing `make` arguments
- Cross-compiling (if notebook is running inside of Docker)
- Running and stopping Bela programs
- Copy files from and to the Bela filesystem (and move and delete ? these two functionalities are more advanced and hence maybe unnecessary in the python API, we don't need to the python API to replace the CLI)

### earlier flowcharts
https://www.figma.com/file/Koujbd3kk4SmfBMclB6DJc/daq-bela?type=design&node-id=0%3A1&mode=design&t=NED67CfDs57miwP1-1

https://excalidraw.com/#room=eecee4de7174b892a7a8,3segJWq_E5PHf_XMjrTcZg
