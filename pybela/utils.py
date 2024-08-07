
class _bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def _print_error(message):
    print(_bcolors.FAIL + message + _bcolors.ENDC)


def _print_info(message):
    print(_bcolors.OKBLUE + message + _bcolors.ENDC)


def _print_warning(message):
    print(_bcolors.WARNING + message + _bcolors.ENDC)


def _print_ok(message, end='\n', flush=False):
    print(_bcolors.OKGREEN + message + _bcolors.ENDC, end=end, flush=flush)
