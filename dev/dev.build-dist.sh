# package and upload to pypi
rm -r dist/
pipenv run python -m build --wheel  
pipenv run python -m build --sdist
pipenv run twine check dist/*
# pipenv run twine upload -r testpypi dist/*     
# pipenv run twine upload -r pypi dist/*        
# https://realpython.com/pypi-publish-python-package/#publish-your-package-to-pypi