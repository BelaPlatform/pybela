from .Streamer import Streamer
import asyncio
# TODO check saving


class Monitor(Streamer):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Monitor class

            Args:
                ip (str, optional): Remote address IP. If using internet over USB, the IP won't work, pass "bela.local". Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """

        super(Monitor, self).__init__(ip, port, data_add, control_add)

        # longer queue for monitor since each buffer has only one value
        self.streaming_buffers_queue_length = 2000
        self._mode = "MONITOR"

    @property
    def values(self):
        values = {}
        for var in self.streaming_buffers_queue:
            values[var] = {"timestamps": [], "values": []}
            for _buffer in self.streaming_buffers_queue[var]:
                values[var]["timestamps"].append(_buffer["ref_timestamp"])
                values[var]["values"].append(_buffer["data"])
        return values

    @property
    def monitored_vars(self):
        pass

    def peek(self, variables=[]):
        """ Peek at variables

            Args:
                variables (list, optional): List of variables to peek at. If no variables are specified, stream all watcher variables (default).

            Returns:
                dict: Dictionary of variables with their values
        """

        async def _async_peek(variables):
            # checks types and if no variables are specified, stream all watcher variables (default)
            variables = self._var_arg_checker(variables)
            self._peek_response = {var: None for var in variables}
            self.start_monitoring(variables, [1]*len(variables))
            await self._peek_response_available.wait()
            self._peek_response_available.clear()
            peeked_values = self._peek_response
            # set _peek_response again to None so that peek is not notified every time a new buffer is received (see Streamer._process_data_msg)
            self._peek_response = None
            self.stop_monitoring(variables)

            return peeked_values

        return asyncio.run(_async_peek(variables))

        # using list
        # res = self.list()
        # return {var: next(r["value"] for r in res if r["name"] == var) for var in variables}

    def start_monitoring(self, variables=[], periods=[], saving_enabled=False, saving_filename="var_monitor.txt"):
        """_summary_

        Args:
            variables (list, optional): _description_. Defaults to [].
            period (list, optional): _description_. Defaults to [].
            saving_enabled (bool, optional): _description_. Defaults to False.
            saving_filename (str, optional): _description_. Defaults to "var_monitor.txt".
        """

        variables = self._var_arg_checker(variables)
        periods = self._check_periods(periods, variables)

        self.start_streaming(
            variables, periods, saving_enabled, saving_filename)

    def stop_monitoring(self, variables=[]):
        self.stop_streaming(variables)
        # return only nonempty variables
        return {var: self.values[var] for var in self.values if self.values[var]["timestamps"] != []}
