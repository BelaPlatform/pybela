cd test
# remove virtual env if it exists
if [ -d "test-env" ]; then
    rm -rf test-env
fi
echo "\nCreating test-env..."
python -m venv test-env
source test-env/bin/activate
echo "\nInstalling pybela from dist..." 
pip install ../dist/pybela-1.0.2-py3-none-any.whl
echo "\nRunning test.py..."
python test.py
deactivate
rm -rf test-env