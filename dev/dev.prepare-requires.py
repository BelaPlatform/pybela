def filter_pybela_packages(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    pybela_packages = []
    for line in lines:
        if 'pybela' in line and line.startswith('#'):
            pybela_packages.append(line.split('#')[1].split(' ')[1])
    print(pybela_packages)
    return pybela_packages


def write_pybela_packages_to_file(pybela_packages, output_file_path):
    print(f"Writing pybela packages to file: {output_file_path}")
    with open(output_file_path, 'w') as file:
        for package in pybela_packages:
            file.write(f"{package}\n")


file_path = 'pip-chill.txt'
output_file_path = 'requirements.txt'
pybela_packages = filter_pybela_packages(file_path)
write_pybela_packages_to_file(pybela_packages, output_file_path)
