# Check if $1 is passed
if [ -z "$1" ]; then
  printf "Error: Pass version. Usage: sh dev.test-dist.sh <version>"
  exit 1
fi

uv run twine check dist/pybela-$1-py3-none-any.whl 
uv run twine check dist/pybela-$1.tar.gz


cd test

# remove virtual env if it exists
if [ -d "test-env" ]; then
    rm -rf test-env
fi

printf "\nCreating test-env..."
python -m venv test-env
source test-env/bin/activate
printf "\nInstalling pybela from dist..." 
pip install ../dist/pybela-$1-py3-none-any.whl


printf "\n>>Copying test project files to Bela...\n"
rsync -avL bela-test root@bela.local:Bela/projects/

printf "\n>>Compile the and run the test project on Bela...\n"
ssh root@bela.local 'make -C /root/Bela run PROJECT=bela-test' & # check if this builds

sleep 2

printf "\nRunning test.py..."
python test.py
deactivate
rm -rf test-env