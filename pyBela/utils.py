
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_error(message):
    print(bcolors.FAIL + message + bcolors.ENDC)


def print_info(message):
    print(bcolors.OKBLUE + message + bcolors.ENDC)


def print_warning(message):
    print(bcolors.WARNING + message + bcolors.ENDC)


def print_ok(message, end='\n', flush=False):
    print(bcolors.OKGREEN + message + bcolors.ENDC, end=end, flush=flush)
