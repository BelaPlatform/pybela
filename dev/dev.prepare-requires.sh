# generate requirements.txt
pipenv run pip-chill --no-chill -v > pip-chill.txt
pipenv run python dev/dev.prepare-requires.py
rm pip-chill.txt