from .Watcher import Watcher
from .utils import print_info, print_error


class Controller(Watcher):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """Controller class

        Args:
                ip (str, optional): Remote address IP. If using internet over USB, the IP won't work, pass "bela.local". Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """
        super(Controller, self).__init__(ip, port, data_add, control_add)

        self._mode = "CONTROL"

    def start_controlling(self, variables=[]):
        """Starts the controller"""
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "control", "watchers": variables}]})
        print_info(
            f"Started controlling variables {variables}... Run stop_controlling() to stop controlling the variable values.")
        # TODO wait until list returns controlled otherwise throw error

    def stop_controlling(self, variables=[]):
        """Stops the controller"""
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "uncontrol", "watchers": variables}]})

        # TODO wait until list returns not controlled otherwise throw error

        print_info(f"Stopped controlling variables {variables}.")
        pass

    def send_ctrl_value(self, variables=[], values=[]):
        """Sends the control values"""
        assert len(variables) == len(
            values), "The number of variables and values should be the same."

        # TODO check value types

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "set", "watchers": variables, "values": values}]})
        pass
