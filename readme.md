# Prototypes for pyBelaAPI
- `cpp/PyBela.h`: Runtime cpp pyBela pyBelaAPI -- to be called and used inside of a Bela program
- `python/pyBela.py`: Python Bela API -- interacts with the cpp API but can also interact outside of the Bela program (i.e., non-runtime operations, like moving and creating files, running and stopping Bela programs).

So there's still lacking a prototype for a cpp library that will listen and execute non-runtime commands comming from python (like running and stopping Bela programs) -- I am not very sure how to do this and this is probably better implemented by someone familiar with the Bela core 
