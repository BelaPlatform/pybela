from .Streamer import Streamer
import asyncio


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

        self._mode = "MONITOR"

    def connect(self):
        if (super().connect()):
            # longer queue for monitor since each buffer has only one value
            self.streaming_buffers_queue_length = 2000

    @property
    def values(self):
        """ Get monitored values from last monitoring session

        Returns:
            dict of dicts of list: Dict containing the monitored buffers for each variable in the watcher
        """
        values = {}
        for var in self.streaming_buffers_queue:
            values[var] = {"timestamps": [], "values": []}
            for _buffer in self.streaming_buffers_queue[var]:
                values[var]["timestamps"].append(_buffer["timestamp"])
                values[var]["values"].append(_buffer["value"])
        return values

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

    def start_monitoring(self, variables=[], periods=[], saving_enabled=False, saving_filename="monitor.txt", saving_dir="/."):
        """
        Starts the monitoring session. The session can be stopped with stop_monitoring().

        If no variables are specified, all watcher variables are monitored. If saving_enabled is True, the monitored data is saved to a local file. If saving_filename is None, the default filename is used with the variable name appended to its start. The filename is automatically incremented if it already exists. 

        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            periods (list, optional): List of monitoring periods. Defaults to [].
            saving_enabled (bool, optional): Enables/disables saving monitored data to local file. Defaults to False.
            saving_filename (str, optional) Filename for saving the monitored data. Defaults to None.
            saving_dir (str, optional): Directory for saving the monitored data. Defaults to "/.".
        """

        variables = self._var_arg_checker(variables)
        periods = self._check_periods(periods, variables)

        self.start_streaming(
            variables=variables, periods=periods, saving_enabled=saving_enabled, saving_filename=saving_filename, saving_dir=saving_dir)

    def monitor_n_values(self, variables=[], periods=[], n_values=1000, saving_enabled=False, saving_filename="monitor.txt"):
        """
        Monitors a given number of values. Since the data comes in buffers of a predefined size, always an extra number of frames will be monitored (unless the number of frames is a multiple of the buffer size). 

        Note: This function will block the main thread until n_values have been monitored. Since the monitored values come in blocks, the actual number of returned frames monitored may be higher than n_values, unless n_values is a multiple of the block size (monitor._streaming_block_size).

        To avoid blocking, use the async version of this function:
            monitor_task = asyncio.create_task(monitor.async_monitor_n_values(variables, n_values, periods, saving_enabled, saving_filename))
        and retrieve the monitored buffer using:
             monitored_buffers_queue = await monitor_task

        Args:
            variables (list, optional): List of variables to be monitored. Defaults to [].
            periods (list, optional): List of monitoring periods. Defaults to [].
            n_values (int, optional): Number of values to monitor for each variable. Defaults to 1000.
            delay (int, optional): _description_. Defaults to 0.
            saving_enabled (bool, optional): Enables/disables saving monitored data to local file. Defaults to False.
            saving_filename (_type_, optional) Filename for saving the monitored data. Defaults to None.

        Returns:
            monitored_buffers_queue (dict): Dict containing the monitored buffers for each streamed variable.
        """
        variables = self._var_arg_checker(variables)
        periods = self._check_periods(periods, variables)
        self.stream_n_values(variables, periods, n_values,
                             saving_enabled, saving_filename)
        return self.values

    async def async_monitor_n_values(self, variables=[], periods=[], n_values=1000, saving_enabled=False, saving_filename=None):
        """ 
        Asynchronous version of monitor_n_values(). Usage: 
            monitor_task = asyncio.create_task(monitor.async_monitor_n_values(variables, periods, n_values, saving_enabled, saving_filename)) 
        and retrieve the monitored buffer using:
            monitoring_buffers_queue = await monitor_task


        Args:
            variables (list, optional): List of variables to be monitored. Defaults to [].
            periods (list, optional): List of monitoring period. Defaults to [].
            n_values (int, optional): Number of values to monitor for each variable. Defaults to 1000.
            saving_enabled (bool, optional): Enables/disables saving monitored data to local file. Defaults to False.
            saving_filename (_type_, optional) Filename for saving the monitored data. Defaults to None.

        Returns:
            deque: Monitored buffers queue
        """
        variables = self._var_arg_checker(variables)
        periods = self._check_periods(periods, variables)

        self.async_stream_n_values(variables, periods, n_values,
                                   saving_enabled, saving_filename)

    def stop_monitoring(self, variables=[]):
        """
        Stops the current monitoring session for the given variables. If no variables are passed, the monitoring of all variables is interrupted.

        Args:
            variables (list, optional): List of variables to stop monitoring. Defaults to [].

        Returns:
            dict of dicts of lists: Dict containing the monitored buffers for each monitored variable
        """
        self.stop_streaming(variables)
        self._monitored_vars = None  # reset monitored variables
        # return only nonempty variables
        return {var: self.values[var] for var in self.values if self.values[var]["timestamps"] != []}

    def load_data_from_file(self, filename, flatten=True):
        """
        Loads data from a file saved through the saving_enabled function in start_monitoring() or monitor_n_values(). The file should contain a list of dicts, each dict containing a variable name and a list of values. The list of dicts should be separated by newlines.
        Args:
            filename (str): Filename
            flatten (bool, optional): If True, the returned list of values is flattened. Defaults to True.

        Returns:
            dict of lists: Dict with "timestamps" and "values" list if flatten is True, otherwise a list of dicts with "timestamp" and "value" keys.
        """
        loaded_buffers = super().load_data_from_file(filename)
        if flatten:
            flatten_loaded_buffers = {"timestamps": [], "values": []}
            for _buffer in loaded_buffers:
                flatten_loaded_buffers["timestamps"].append(
                    _buffer["timestamp"])
                flatten_loaded_buffers["values"].append(_buffer["value"])
            return flatten_loaded_buffers
        else:
            return loaded_buffers
