To build the docs you will need to install `pandoc` to convert the `readme.md` into `rst` (the format used by `sphinx`, the docs builder). You can see the installation instructions [here](https://pandoc.org/installing.html).

Then you can build the docs with:

```bash
rm -r _build
pandoc -s ../readme.md -o readme.rst
pipenv run sphinx-build -M html . _build
```
