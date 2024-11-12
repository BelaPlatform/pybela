cd test
# remove virtual env if it exists
if [ -d "test-env" ]; then
    rm -rf test-env
fi
python -m venv test-env
source test-env/bin/activate 
pip install ../dist/pybela-1.0.1-py3-none-any.whl
python test.py
deactivate
rm -rf test-env