rm -r docs/_build
uv run pandoc -s readme.md -o docs/readme.rst
uv run sphinx-build -M html docs/ docs/_build
open docs/_build/html/index.html  