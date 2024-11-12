rm -r docs/_build
pipenv run pandoc -s readme.md -o docs/readme.rst
pipenv run sphinx-build -M html docs/ docs/_build
open docs/_build/html/index.html  