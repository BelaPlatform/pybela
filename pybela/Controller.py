import asyncio
from .Watcher import Watcher
from .utils import _print_info, _print_warning


class Controller(Watcher):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """Controller class
        Note: All values set with the controller class will be only visible through the "get_value()" method, or the "value" field in the list() function. Values streamed with the streamer, logger or monitor classes will not be affected.

        Args:
                ip (str, optional): Remote address IP. If using internet over USB, the IP won't work, pass "bela.local". Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """
        super(Controller, self).__init__(ip, port, data_add, control_add)

        self._mode = "CONTROL"

    def start_controlling(self, variables=[]):
        """Starts controlling given variables. This function will block until all requested variables are set to 'controlled' in the list. 
        Note: All values set with the controller class will be only visible through the "get_value()" method, or the "value" field in the list() function. Values streamed with the streamer, logger or monitor classes will not be affected.

        Args:
            variables (list, optional): List of variables to control. If no variables are specified, stream all watcher variables (default).        
        """

        variables = self._var_arg_checker(variables)

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "control", "watchers": variables}]})

        async def async_wait_for_control_mode_to_be_set(variables=variables):
            # wait for variables to be set as 'controlled' in list
            _controlled_status = self.get_controlled_status(
                variables)  # avoid multiple calls to list
            while not all([_controlled_status[var] for var in variables]):
                await asyncio.sleep(0.5)

        asyncio.run(async_wait_for_control_mode_to_be_set(variables=variables))

        _print_info(
            f"Started controlling variables {variables}... Run stop_controlling() to stop controlling the variable values.")

    def stop_controlling(self, variables=[]):
        """Stops controlling given variables. This function will block until all requested variables are set to 'uncontrolled' in the list. 
        Note: All values set with the controller class will be only visible through the "get_value()" method, or the "value" field in the list() function.

        Args:
            variables (list, optional): List of variables to control. If no variables are specified, stream all watcher variables (default).        
        """

        variables = self._var_arg_checker(variables)

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "uncontrol", "watchers": variables}]})

        async def async_wait_for_control_mode_to_be_set(variables=variables):
            # wait for variables to be set as 'uncontrolled' in list
            _controlled_status = self.get_controlled_status(
                variables)  # avoid multiple calls to list
            while all([_controlled_status[var] for var in variables]):
                await asyncio.sleep(0.5)

        asyncio.run(async_wait_for_control_mode_to_be_set(variables=variables))

        _print_info(f"Stopped controlling variables {variables}.")

    def send_value(self, variables, values):
        """Send a value to the given variables. 
        Note: All values set with this function will be only visible through the "get_value()" method, or the "value" field in the list() function. Values streamed with the streamer, logger or monitor classes will not be affected. 

        Args:
            variables (list, required): List of variables to control.
            values (list, required): Values to be set for each variable.
        """

        assert isinstance(values, list) and len(
            values) > 0, "At least one value per variable should be provided."

        variables = self._var_arg_checker(variables)

        assert len(variables) == len(
            values), "The number of variables and values should be the same."

        for var in variables:
            _type = self.get_prop_of_var(var, "type")

            value = values[variables.index(var)]

            if value % 1 != 0 and _type in ["i", "j"]:
                _print_warning(
                    f"Value {value} is not an integer, but the variable {var} is of type {_type}. Only the integer part will be sent.")

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "set", "watchers": variables, "values": values}]})

    def get_controlled_status(self, variables=[]):
        """Gets the controlled status (controlled or uncontrolled) of the variables

        Args:
            variables (list of str, optional): List of variables to check. Defaults to all variables in the watcher.

        Returns:
            list of str: List of controlled status of the variables
        """
        variables = self._var_arg_checker(variables)
        return {var['name']: var['controlled'] for var in self.list()['watchers'] if var['name'] in variables}

    def get_value(self, variables=[]):
        """ Gets the value of the variables

        Args:
            variables (list of str, optional): List of variables to get the value from. Defaults to all variables in the watcher. 

        Returns:
            list of numbers: List of controlled values of the variables
        """
        variables = self._var_arg_checker(variables)
        return {var['name']: var['value'] for var in self.list()['watchers'] if var['name'] in variables}
