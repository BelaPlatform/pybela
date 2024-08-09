import asyncio.base_subprocess
import json
import copy
import os
import glob
import asyncio
import aiofiles  # async file i/o
from collections import deque  # circular buffers
from itertools import cycle
import warnings
import re
import struct

import bokeh.plotting
import bokeh.io
import bokeh.driving
from bokeh.resources import INLINE
from .Watcher import Watcher
from .utils import _print_info, _print_error, _print_warning


class Streamer(Watcher):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Streamer class

            Args:
                ip (str, optional): Remote address IP. If using internet over USB, the IP won't work, pass "bela.local". Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """

        super(Streamer, self).__init__(ip, port, data_add, control_add)

        # -- streaming --
        self._streaming_mode = "OFF"  # OFF, FOREVER, N_VALUES, PEEK :: this flag prevents writing into the streaming buffer unless requested by the user using the start/stop_streaming() functions
        self._streaming_buffer_available = asyncio.Event()
        # number of streaming buffers (not of data points!)
        self._streaming_buffers_queue_length = 1000
        self._streaming_buffers_queue = None
        self.last_streamed_buffer = {}

        # -- on data/block callbacks --
        self._processed_data_msg_queue = asyncio.Queue()
        self._on_buffer_callback_is_active = False
        self._on_buffer_callback_worker_task = None
        self._on_block_callback_is_active = False
        self._on_block_callback_worker_task = None

        # -- save --
        self._saving_enabled = False
        self._saving_filename = None
        self._saving_task = None
        self._active_saving_tasks = []
        self._saving_file_locks = {}

        # -- monitor --
        # stores the list of monitored variables for each monitored session. cleaned after each monitoring session. used to avoid calling list() every time a new message is parsed
        self._monitored_vars = None
        self._peek_response_available = asyncio.Event()
        self._peek_response = None

        self._mode = "STREAM"

    # --- public methods --- #

    # - setters & getters

    @property
    def monitored_vars(self):
        """ Returns a list of monitored variables. If no variables are monitored, returns an empty list.

        Returns:
            list: list of monitored variables
        """
        if self._monitored_vars is None:  # avoids calling list() every time a new message is parsed
            _list = self.list()
            self._monitored_vars = self._filtered_watcher_vars(
                _list["watchers"], lambda var: var["monitor"])
            if self._monitored_vars == []:
                self._monitored_vars = None
        return self._monitored_vars

    @property
    def streaming_buffers_queue_length(self):
        """
        Returns:
            int: maximum number of streaming buffers allowed in self.streaming_buffers_queue
        """
        return self._streaming_buffers_queue_length

    @streaming_buffers_queue_length.setter
    def streaming_buffers_queue_length(self, value):
        """Sets the maximum number of streaming buffers allowed in self.streaming_buffers_queue. Warning: setting the streaming buffer value will result in deleting the current streaming buffer queue.
        """
        # TODO resize in terms of number of datapoints instead of number of buffers?
        self._streaming_buffers_queue_length = value
        self._streaming_buffers_queue = {var["name"]: deque(
            maxlen=self._streaming_buffers_queue_length) for var in self.watcher_vars}  # resize streaming buffer

    @property
    def streaming_buffers_queue(self):
        """Returns a dict where each key corresponds to a variable and each item to the variable's buffer queue. The queue has maximum length determined by streamer.streaming_buffers_queue_length. Each item of the queue is a received buffer of the form {"frame: int, "data": {"var1": [val1, val2, ...], "var2": [val1, val2, ...], ...} }

        Returns:
            dict: streaming buffers queue
        """
        # returns a dict of lists instead of a dict of dequeues
        return {key: list(value) for key, value in self._streaming_buffers_queue.items()}

    @property
    def streaming_buffers_data(self):
        """Returns a dict where each key corresponds to a variable and each value to a flat list of the streamed values. Does not return timestamps of each datapoint since that depends on how often the variables are reassigned in the Bela code.
        Returns:
            dict: Dict of flat lists of streamed values.
        """
        data = {}
        for var in self.streaming_buffers_queue:
            data[var] = []
            for _buffer in self.streaming_buffers_queue[var]:
                data[var].extend(_buffer["data"] if self._mode !=
                                 "MONITOR" else [_buffer["value"]])
        return data

    # - streaming methods

    def __streaming_common_routine(self, variables=[], saving_enabled=False, saving_filename="var_stream.txt", saving_dir="./", on_buffer_callback=None, on_block_callback=None, callback_args=()):

        if self.is_streaming():
            _print_warning("Stopping previous streaming session...")
            self.stop_streaming()  # stop any previous streaming

        if not self.is_connected():
            _print_warning(
                f'{"Monitor" if self._mode=="MONITOR" else "Streamer" } is not connected to Bela. Run {"monitor" if self._mode=="MONITOR" else "streamer"}.connect() first.')
            return 0
        self._streaming_buffers_queue = {var["name"]: deque(
            maxlen=self._streaming_buffers_queue_length) for var in self.watcher_vars}
        self.last_streamed_buffer = {
            var["name"]: {"data": [], "timestamps": []} for var in self.watcher_vars}

        if not os.path.exists(saving_dir):
            os.makedirs(saving_dir)

        self._saving_enabled = True if saving_enabled else False
        self._saving_filename = self._generate_filename(
            saving_filename, saving_dir) if saving_enabled else None

        self._processed_data_msg_queue = asyncio.Queue()  # clear processed data queue

        async def async_callback_workers():

            if on_block_callback and on_buffer_callback:
                _print_error(
                    "Error: Both on_buffer_callback and on_block_callback cannot be enabled at the same time.")
                return 0
            if on_buffer_callback:
                self._on_buffer_callback_is_active = True
                self._on_buffer_callback_worker_task = asyncio.create_task(
                    self.__async_on_buffer_callback_worker(on_buffer_callback, callback_args))

            elif on_block_callback:
                self._on_block_callback_is_active = True
                self._on_block_callback_worker_task = asyncio.create_task(
                    self.__async_on_block_callback_worker(on_block_callback, callback_args, variables))

        asyncio.run(async_callback_workers())

        # checks types and if no variables are specified, stream all watcher variables (default)
        return self._var_arg_checker(variables)

    def start_streaming(self, variables=[], periods=[], saving_enabled=False, saving_filename="var_stream.txt", saving_dir="./", on_buffer_callback=None, on_block_callback=None, callback_args=()):
        """
        Starts the streaming session. The session can be stopped with stop_streaming().

        If no variables are specified, all watcher variables are streamed. If saving_enabled is True, the streamed data is saved to a local file. If saving_filename is None, the default filename is used with the variable name appended to its start. The filename is automatically incremented if it already exists. 

        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            periods (list, optional): List of streaming periods. Streaming periods are used by the monitor and will be ignored if in streaming mode. Defaults to [].
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (str, optional) Filename for saving the streamed data. Defaults to None.
            on_buffer_callback (function, optional). Callback function that is called every time a buffer is received. The callback function should take a single argument, the buffer. Accepts asynchronous functions (defined with async def). Defaults to None.
            on_block_callback (function, optional). Callback function that is called every time a block of buffers is received. A block of buffers is a list of buffers, one for each streamed variable. The callback function should take a single argument, a list of buffers. Accepts asynchronous functions (defined with async def). Defaults to None.
            callback_args (tuple, optional): Arguments to pass to the callback functions. Defaults to ().

        """

        variables = self.__streaming_common_routine(
            variables, saving_enabled, saving_filename, saving_dir, on_buffer_callback, on_block_callback, callback_args)

        # commented because then you can only start streaming on variables whose values have been previously assigned in the Bela code
        # not useful for the Sender function (send a buffer from the laptop and stream it through the watcher)
        # async def async_wait_for_streaming_to_start():  # ensures that when function returns streaming has started
        # if self._mode == "STREAM":
        #     while set([var["name"] for var in self.watched_vars]) != set(variables):
        #         await asyncio.sleep(0.1)
        # elif self._mode == "MONITOR":
        #     while not all(self._streaming_buffers_queue_insertion_counts[var] > 0 for var in variables):
        #             await asyncio.sleep(0.1)

        self._streaming_mode = "FOREVER" if self._peek_response is None else "PEEK"
        if self._mode == "STREAM":
            if periods != []:
                warnings.warn(
                    "Periods list is ignored in streaming mode STREAM")
            self.send_ctrl_msg(
                {"watcher": [{"cmd": "watch", "watchers": variables}]})
            # asyncio.run(async_wait_for_streaming_to_start())
            _print_info(
                f"Started streaming variables {variables}... Run stop_streaming() to stop streaming.")
        elif self._mode == "MONITOR":
            periods = self._check_periods(periods, variables)
            self.send_ctrl_msg(
                {"watcher": [{"cmd": "monitor", "watchers": variables, "periods": periods}]})
            # asyncio.run(async_wait_for_streaming_to_start())
            if self._streaming_mode == "FOREVER":
                _print_info(
                    f"Started monitoring variables {variables}... Run stop_monitoring() to stop monitoring.")
            elif self._streaming_mode == "PEEK":
                _print_info(f"Peeking at variables {variables}...")

    def stop_streaming(self, variables=[]):
        """
        Stops the current streaming session for the given variables. If no variables are passed, the streaming of all variables is interrupted.

        Args:
            variables (list, optional): List of variables to stop streaming. Defaults to [].

        Returns:
            streaming_buffers_queue (dict): Dict containing the streaming buffers for each streamed variable.
        """
        async def async_stop_streaming(variables=[]):
            # self.stop()

            _previous_streaming_mode = copy.copy(self._streaming_mode)

            self._streaming_mode = "OFF"

            if self._saving_enabled:
                self._saving_enabled = False
                self._saving_filename = None
                # await all active saving tasks
                await asyncio.gather(*self._active_saving_tasks, return_exceptions=True)
                self._active_saving_tasks.clear()

            if variables == []:
                # if no variables specified, stop streaming all watcher variables (default)
                variables = [var["name"] for var in self.watcher_vars]

            if self._mode == "STREAM" and _previous_streaming_mode != "SCHEDULE":
                self.send_ctrl_msg(
                    {"watcher": [{"cmd": "unwatch", "watchers": variables}]})
                _print_info(f"Stopped streaming variables {variables}...")
            elif self._mode == "MONITOR" and _previous_streaming_mode != "SCHEDULE":
                self.send_ctrl_msg(
                    {"watcher": [{"cmd": "monitor", "periods": [0]*len(variables),  "watchers": variables}]})  # setting period to 0 disables monitoring
                if not _previous_streaming_mode == "PEEK":
                    _print_info(f"Stopped monitoring variables {variables}...")
                    self._processed_data_msg_queue = asyncio.Queue()  # clear processed data queue
                self._on_buffer_callback_is_active = False
                if self._on_buffer_callback_worker_task:
                    self._on_buffer_callback_worker_task.cancel()
                self._on_block_callback_is_active = False
                if self._on_block_callback_worker_task:
                    self._on_block_callback_worker_task.cancel()

        return asyncio.run(async_stop_streaming(variables))

    def schedule_streaming(self, variables=[], timestamps=[], durations=[], saving_enabled=False, saving_filename="var_stream.txt", saving_dir="./", on_buffer_callback=None, on_block_callback=None, callback_args=()):
        """Schedule streaming of variables. The streaming session can be stopped with stop_streaming().

        Args:

            variables (list, optional): List of variables to be streamed. Defaults to [].
            timestamps (list, optional): Timestamps to start streaming (one for each variable). Defaults to [].
            durations (list, optional): Durations to stream for (one for each variable). Defaults to [].
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (str, optional) Filename for saving the streamed data. Defaults to None.
            saving_dir (str, optional): Directory for saving the streamed data files. Defaults to "./".
            on_buffer_callback (function, optional). Callback function that is called every time a buffer is received. The callback function should take a single argument, the buffer. Accepts asynchronous functions (defined with async def). Defaults to None.
            on_block_callback (function, optional). Callback function that is called every time a block of buffers is received. A block of buffers is a list of buffers, one for each streamed variable. The callback function should take a single argument, a list of buffers. Accepts asynchronous functions (defined with async def). Defaults to None.
            callback_args (tuple, optional): Arguments to pass to the callback functions. Defaults to ().
        """

        variables = self.__streaming_common_routine(
            variables, saving_enabled, saving_filename, saving_dir, on_buffer_callback, on_block_callback, callback_args)

        self._streaming_mode = "SCHEDULE"

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "watch", "timestamps": timestamps, "durations": durations, "watchers": variables}]})

        async def async_check_if_variables_have_been_streamed_and_stop():
            # poll to see when variables start streaming and when they stop
            started_streaming_vars = []
            finished_streaming_vars = []

            while not all(var in finished_streaming_vars for var in variables):

                for var in [v["name"] for v in self.watched_vars]:
                    if var not in started_streaming_vars:
                        started_streaming_vars.append(var)
                        _print_info(f"Started streaming {var}...")

                for var in started_streaming_vars:
                    if var not in [v["name"] for v in self.watched_vars]:
                        finished_streaming_vars.append(var)
                        _print_info(f"Stopped streaming {var}")

                await asyncio.sleep(0.1)

            self.stop_streaming()

        asyncio.run(
            async_check_if_variables_have_been_streamed_and_stop())

    def stream_n_values(self, variables=[], periods=[], n_values=1000, saving_enabled=False, saving_filename=None, saving_dir="./", on_buffer_callback=None, on_block_callback=None, callback_args=()):
        """
        Streams a given number of values. Since the data comes in buffers of a predefined size, always an extra number of frames will be streamed (unless the number of frames is a multiple of the buffer size). 

        Note: This function will block the main thread until n_values have been streamed. Since the streamed values come in blocks, the actual number of returned frames streamed may be higher than n_values, unless n_values is a multiple of the block size (streamer._streaming_block_size).

        To avoid blocking, use the async version of this function:
            stream_task = asyncio.create_task(streamer.async_stream_n_values(variables, n_values, periods, saving_enabled, saving_filename))
        and retrieve the streaming buffer using:
             streaming_buffers_queue = await stream_task

        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            periods (list, optional): List of streaming periods. Streaming periods are used by the monitor and will be ignored if in streaming mode. Defaults to [].
            n_values (int, optional): Number of values to stream for each variable. Defaults to 1000.
            delay (int, optional): _description_. Defaults to 0.
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (str, optional) Filename for saving the streamed data. Defaults to None.
            saving_dir (str, optional): Directory for saving the streamed data. Defaults to "./".
            on_buffer_callback (function, optional). Callback function that is called every time a buffer is received. The callback function should take a single argument, the buffer. Accepts asynchronous functions (defined with async def). Defaults to None.
            on_block_callback (function, optional). Callback function that is called every time a block of buffers is received. A block of buffers is a list of buffers, one for each streamed variable. The callback function should take a single argument, a list of buffers. Accepts asynchronous functions (defined with async def). Defaults to None.
            callback_args (tuple, optional): Arguments to pass to the callback functions. Defaults to ().

        Returns:
            streaming_buffers_queue (dict): Dict containing the streaming buffers for each streamed variable.
        """
        return asyncio.run(self.async_stream_n_values(variables, periods, n_values, saving_enabled, saving_filename, saving_dir, on_buffer_callback, on_block_callback, callback_args))

    async def async_stream_n_values(self, variables=[], periods=[], n_values=1000, saving_enabled=False, saving_filename="var_stream.txt", saving_dir="./", on_buffer_callback=None, on_block_callback=None, callback_args=()):
        """ 
        Asynchronous version of stream_n_values(). Usage: 
            stream_task = asyncio.create_task(streamer.async_stream_n_values(variables, n_values, saving_enabled, saving_filename)) 
        and retrieve the streaming buffer using:
            streaming_buffers_queue = await stream_task


        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            periods (list, optional): List of streaming periods. Streaming periods are used by the monitor and will be ignored if in streaming mode. Defaults to [].
            n_values (int, optional): Number of values to stream for each variable. Defaults to 1000.
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (str, optional) Filename for saving the streamed data. Defaults to None.
            saving_dir (str, optional): Directory for saving the streamed data. Defaults to "./".
            on_buffer_callback (function, optional). Callback function that is called every time a buffer is received. The callback function should take a single argument, the buffer. Accepts asynchronous functions (defined with async def). Defaults to None.
            on_block_callback (function, optional). Callback function that is called every time a block of buffers is received. A block of buffers is a list of buffers, one for each streamed variable. The callback function should take a single argument, a list of buffers. Accepts asynchronous functions (defined with async def). Defaults to None.
            callback_args (tuple, optional): Arguments to pass to the callback functions. Defaults to ().

        Returns:
            deque: Streaming buffers queue
        """
        # resizes the streaming buffer size to n_values and returns it when full

        variables = self.__streaming_common_routine(
            variables, saving_enabled, saving_filename, saving_dir, on_buffer_callback, on_block_callback, callback_args)

        self._streaming_mode = "N_VALUES"  # flag cleared in __rec_msg_callback

        if self._mode == "STREAM":
            # if mode stream, each buffer has m values and we need to calc the min buffers needed to supply n_values

            # variables might have different buffer sizes -- the code below finds the minimum number of buffers needed to stream n_values for all variables
            buffer_sizes = [
                self.get_data_length(var["type"], var["timestamp_mode"])
                for var in self.watcher_vars if var["name"] in variables]

            # TODO add a warning when there's different buffer sizes ?

            # ceiling division
            n_buffers = -(-n_values // min(buffer_sizes))
            # using setter to automatically resize buffer
            self.streaming_buffers_queue_length = n_buffers

            if periods != []:
                warnings.warn(
                    "Periods list is ignored in streaming mode STREAM")
            self.send_ctrl_msg(
                {"watcher": [{"cmd": "unwatch", "watchers": [var["name"] for var in self.watcher_vars]}, {"cmd": "watch", "watchers": variables}]})
            _print_info(
                f"Streaming {n_values} values for variables {variables}...")

        elif self._mode == "MONITOR":
            # if mode monitor, each buffer has 1 value so the length of the streaming buffer queue is equal to n_values
            self.streaming_buffers_queue_length = n_values

            periods = self._check_periods(periods, variables)
            self.send_ctrl_msg(
                {"watcher": [{"cmd": "monitor", "watchers": variables, "periods": periods}]})
            _print_info(
                f"Monitoring {n_values} values for variables {variables} with periods {periods}...")

        # await until streaming buffer is full
        await self._streaming_buffer_available.wait()
        self._streaming_buffer_available.clear()

        # turns off listener, unwatches variables
        self.stop_streaming(variables)
        if self._mode == "MONITOR":
            self._monitored_vars = None  # reset monitored vars

        return self.streaming_buffers_queue

    # callbacks

    async def __async_on_buffer_callback_worker(self, on_buffer_callback, callback_args):
        while self._on_buffer_callback_is_active and self.is_streaming():
            if not self._processed_data_msg_queue.empty():
                msg = await self._processed_data_msg_queue.get()
                self._processed_data_msg_queue.task_done()
                try:
                    if asyncio.iscoroutinefunction(on_buffer_callback):
                        if callback_args != () and type(callback_args) == tuple:
                            await on_buffer_callback(msg, *callback_args)
                        elif callback_args != ():
                            await on_buffer_callback(msg, callback_args)
                        else:
                            await on_buffer_callback(msg)
                    else:
                        if callback_args != () and type(callback_args) == tuple:
                            on_buffer_callback(msg, *callback_args)
                        elif callback_args != ():
                            on_buffer_callback(msg, callback_args)
                        else:
                            on_buffer_callback(msg)
                except Exception as e:
                    _print_error(
                        f"Error in on_buffer_callback: {e}")

            await asyncio.sleep(0.0001)

    async def __async_on_block_callback_worker(self, on_block_callback, callback_args, variables):
        while self._on_block_callback_is_active and self.is_streaming():
            msgs = []
            for var in variables:
                # if not self._processed_data_msg_queue.empty():
                msg = await asyncio.wait_for(self._processed_data_msg_queue.get(), timeout=1)
                msgs.append(msg)
                self._processed_data_msg_queue.task_done()
            if len(msgs) == len(variables):
                try:
                    if asyncio.iscoroutinefunction(on_block_callback):
                        if callback_args != () and type(callback_args) == tuple:
                            await on_block_callback(msgs, *callback_args)
                        elif callback_args != ():
                            await on_block_callback(msgs, callback_args)
                        else:
                            await on_block_callback(msgs)
                    else:
                        if callback_args != () and type(callback_args) == tuple:
                            on_block_callback(msgs, *callback_args)
                        elif callback_args != ():
                            on_block_callback(msgs, callback_args)
                        else:
                            on_block_callback(msgs)

                except Exception as e:
                    _print_error(
                        f"Error in on_block_callback: {e}")

            await asyncio.sleep(0.001)

    # send

    def send_buffer(self, buffer_id, buffer_type, buffer_length, data_list, verbose=False):
        """
        Sends a buffer to Bela. The buffer is packed into binary format and sent over the websocket.

        Args:
            buffer_id (int): Buffer id
            buffer_type (str): Buffer type. Supported types are 'i' (int), 'f' (float), 'j' (uint), 'd' (double), 'c' (char).
            buffer_length (int): Buffer length
            data_list (list): List of data to be sent
        """
        # Pack the data into binary format
        # >I means big-endian unsigned int, 4s means 4-byte string, pad with x for empty bytes

        idtypestr = struct.pack('<I4sI4x', buffer_id,
                                buffer_type.encode(), buffer_length)
        format_str = buffer_type * len(data_list)
        binary_data = struct.pack(format_str, *data_list)
        self._send_msg(self.ws_data_add, idtypestr + binary_data)
        if verbose:
            _print_info(
                f"Sent buffer {buffer_id} of type {buffer_type} with length {buffer_length}...")

    # - utils

    def is_streaming(self):
        """Returns True if the streamer is currently streaming, False otherwise.

        Returns:
            bool: Streaming status bool
        """
        return True if self._streaming_mode != "OFF" else False

    def flush_queue(self):
        """Flushes the streaming buffers queue. The queue is emptied and the insertion counts are reset to 0.
        """
        self._streaming_buffers_queue = {var["name"]: deque(
            maxlen=self._streaming_buffers_queue_length) for var in self.watcher_vars}

    def load_data_from_file(self, filename):
        """
        Loads data from a file saved through the saving_enabled function in start_streaming() or stream_n_values(). The file should contain a list of dicts, each dict containing a variable name and a list of values. The list of dicts should be separated by newlines.
        Args:
            filename (str): Filename

        Returns:
            list: List of values loaded from file
        """
        try:
            data = []
            with open(filename, "r") as f:
                while True:
                    line = f.readline()
                    if not line:
                        break
                    try:
                        data.append(json.loads(line))
                    except EOFError:  # reached end of file
                        break
        except Exception as e:
            _print_error(f"Error while loading data from file: {e}")
            return None

        return data

    # - plotting

    def _bokeh_plot_data_app(self,
                             data,
                             x_var,
                             y_vars,
                             y_range=None,
                             rollover=None,
                             plot_update_delay=90):
        """Return a function defining a Bokeh app for streaming. The app is called in plot_data().
        Args:
            data (dict): Dict containing the data to be plotted. The dict should have the following structure: {"var1": {"data": [val1, val2, ...], "timestamps": [ts1, ts2, ...]}, "var2": {"data": [val1, val2, ...], "timestamps": [ts1, ts2, ...]}, ...}
            x_var (str): Variable to be plotted on the x axis
            y_vars (list): List of variables to be plotted on the y axis
            y_range (tuple, optional): Tuple containing the y axis range. Defaults to None. If none is given, the y axis range is automatically resized to fit the data.
            rollover (int, optional): Number of data points to keep on the plot. Defaults to None.
            plot_update_delay (int, optional): Delay between plot updates in ms. Defaults to 90.
        """
        # TODO add variable checkers

        def _app(doc):
            # Instantiate figures
            p = bokeh.plotting.figure(
                frame_width=500,
                frame_height=175,
                x_axis_label="timestamps",
                y_axis_label="value",
            )

            if y_range is not None:
                p.y_range = bokeh.models.Range1d(y_range[0], y_range[1])

            # No padding on x_range makes data flush with end of plot
            p.x_range.range_padding = 0

            # Create a dictionary to store ColumnDataSource instances for each y_var
            template = {"timestamps": [], **{var: [] for var in data}}
            source = bokeh.models.ColumnDataSource(template)

            # # Create line glyphs for each y_var
            colors = cycle([
                "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
                "#bcbd22", "#17becf", "#1a55FF", "#FF1A1A"
            ])
            for y_var in y_vars:
                p.line(source=source, x="timestamps",
                       y=y_var, line_color=next(colors), legend_label=y_var)

            @bokeh.driving.linear()
            def update(step):
                # Update plot by streaming in data
                new_data = {"timestamps": [
                    data[x_var]["timestamp"]]if "timestamp" in data[x_var] else data[x_var]["timestamps"]}
                for y_var in y_vars:
                    new_data[y_var] = data[y_var]["data"] if isinstance(
                        data[y_var]["data"], list) else [data[y_var]["data"]]
                source.stream(new_data, rollover)

            doc.add_root(p)
            doc.add_periodic_callback(update, plot_update_delay)
        return _app

    def plot_data(self, x_var, y_vars, y_range=None, plot_update_delay=100, rollover=500):
        """ Plots a bokeh figure with the streamed data. The plot is updated every plot_update_delay ms. The plot is interactive and can be zoomed in/out, panned, etc. The plot is shown in the notebook.

        Args:
            x_var (str): Variable to be plotted on the x axis
            y_vars (list of str): List of variables to be plotted on the y axis
            y_range (float, float):  Tuple containing the y axis range. Defaults to None. If none is given, the y axis range is automatically resized to fit the data.
            plot_update_delay (int, optional): Delay between plot updates in ms. Defaults to 100.
            rollover (int, optional): Number of data points to keep on the plot. Defaults to 1000.
        """

        if self._mode == "MONITOR":
            raise NotImplementedError(
                "Plotting is not yet supported in monitor mode.")

        # check that x_var and y_vars are either streamed or monitored
        for _var in [x_var, *y_vars]:
            if not (_var in [var["name"] for var in self.watched_vars] or _var in [var["name"] for var in self.monitored_vars]):
                _print_error(
                    f"PlottingError: {_var} is not being streamed or monitored.")
                return

        # check buffer lengths are the same
        # wait until streaming buffers have been populated
        async def wait_for_streaming_buffers_to_arrive():
            while not all(data['data'] for data in {
                    var: _buffer for var, _buffer in self.last_streamed_buffer.items() if var in y_vars}.values()):
                await asyncio.sleep(0.1)
        asyncio.run(wait_for_streaming_buffers_to_arrive())
        if len(y_vars) > 1 and not all([len(self.last_streamed_buffer[y_var]) == len(self.last_streamed_buffer[y_vars[0]]) for y_var in y_vars[1:]]):
            _print_error(
                "PlottingError: plotting buffers of different length is not supported yet. Try using the same timestamp mode and type for your variables...")
            return

        bokeh.io.output_notebook(INLINE)
        bokeh.io.show(self._bokeh_plot_data_app(data={
            var: _buffer for var, _buffer in self.last_streamed_buffer.items() if var in y_vars}, x_var=x_var,
            y_vars=y_vars, y_range=y_range, plot_update_delay=plot_update_delay, rollover=rollover))

    # --- private methods --- #

    async def _process_data_msg(self, msg):
        """ Process data message received from Bela. This function is called by the websocket listener when a data message is received.

        Args:
            msg (bytestring): Data message received from Bela
        """

        global _channel, _type
        try:
            _, __ = _channel, _type
        except NameError:  # initialise global variables to None
            _channel = None
            _type = None

        # in case buffer is received whilst streaming mode is on but parsed after streaming_enabled has changed
        _saving_enabled = copy.copy(self._saving_enabled)
        if self._streaming_mode != "OFF":
            if len(msg) in [3, 4]:  # _channel can be either 1 or 2 bytes long
                # parse buffer header
                _channel, _type = re.search(
                    r'(\d+).*?(\w)', msg.decode()).groups()
                _channel = int(_channel)

                assert _type in ['i', 'f', 'j', 'd',
                                 'c'], f"Unsupported type: {_type}"

                assert _type == self._watcher_vars[_channel][
                    'type'], f"Type mismatch: {_type} != {self._watcher_vars[_channel]['type']}"

                # convert unsigned int to int -- struct does not support unsigned ints
                _type = 'i' if _type == 'j' else _type

            elif len(msg) > 3 and _channel is not None and _type is not None:
                var_name = self._watcher_vars[_channel]['name']
                var_timestamp_mode = self._watcher_vars[_channel]["timestamp_mode"]

                # parse buffer body
                parsed_buffer = self._parse_binary_data(
                    msg, var_timestamp_mode, _type).copy()

                # put in processed_queue if callback is true
                if self._on_buffer_callback_is_active or self._on_block_callback_is_active:
                    await self._processed_data_msg_queue.put({"name": var_name, "buffer": parsed_buffer})

                # fixes bug where data is shifted by period
                _var_streaming_buffers_queue = copy.copy(
                    self._streaming_buffers_queue[var_name])
                _var_streaming_buffers_queue.append(parsed_buffer)
                self._streaming_buffers_queue[var_name] = _var_streaming_buffers_queue

                # populate last streamed buffer
                if self._mode == "STREAM":
                    self.last_streamed_buffer[var_name]["data"] = parsed_buffer["data"]
                    if var_timestamp_mode == "dense":
                        self.last_streamed_buffer[var_name]["timestamps"] = [
                            parsed_buffer["ref_timestamp"] + i for i in range(0, len(parsed_buffer["data"]))]
                    elif var_timestamp_mode == "sparse":  # sparse
                        self.last_streamed_buffer[var_name]["timestamps"] = [
                            parsed_buffer["ref_timestamp"] + i for i in parsed_buffer["rel_timestamps"]]
                elif self._mode == "MONITOR":
                    self.last_streamed_buffer[var_name] = {
                        "timestamp": parsed_buffer["timestamp"], "value": parsed_buffer["value"]}

                # save data to file if saving is enabled
                if _saving_enabled:
                    _saving_var_filename = os.path.join(os.path.dirname(
                        self._saving_filename), f"{var_name}_{os.path.basename(self._saving_filename)}")
                    # save the data asynchronously
                    saving_task = asyncio.create_task(
                        self._save_data_to_file(_saving_var_filename, parsed_buffer))
                    self._active_saving_tasks.append(saving_task)

                # response to .peek() call
                if self._mode == "MONITOR" and self._peek_response is not None:
                    # check that all the watched variables have been received
                    self._peek_response[self._watcher_vars[_channel]["name"]] = {
                        "timestamp": parsed_buffer["timestamp"], "value": parsed_buffer["value"]}
                    # notify peek() that data is available
                    if all(value is not None for value in self._peek_response.values()):
                        self._peek_response_available.set()

                # if streaming buffers queue is full for watched variables and streaming mode is n_values
                if self._streaming_mode == "N_VALUES":
                    obs_vars = self.watched_vars if self._mode == "STREAM" else self.monitored_vars
                    if all(len(self._streaming_buffers_queue[var["name"]]) == self._streaming_buffers_queue_length
                            for var in obs_vars):
                        self._streaming_mode = "OFF"
                        self._streaming_buffer_available.set()

    async def _save_data_to_file(self, filename, msg):
        """ Saves data to file asynchronously. This function is called by _process_data_msg() when a buffer is received and saving is enabled.

        Args:
            filename (str): Filename to save data to
            msg (bytestr): Data message received from Bela
        """
        _msg = copy.copy(msg)
        try:
            # make sure there are not two processes writing to the same file
            if filename not in self._saving_file_locks.keys():
                # create lock for file if it does not exist
                self._saving_file_locks[filename] = asyncio.Lock()

            async with self._saving_file_locks[filename]:
                async with aiofiles.open(filename, "a") as f:
                    _json = json.dumps(copy.copy(_msg))
                    await f.write(_json+"\n")

        except Exception as e:
            _print_error(f"Error while saving data to file: {e}")

        finally:
            await self._async_remove_item_from_list(self._active_saving_tasks, asyncio.current_task())

    def _generate_filename(self, saving_filename, saving_dir="./"):
        """ Generates a filename for saving data by adding the variable name and a number at the end in case the filename already exists to avoid overwriting saved data. Pattern: varname_filename__idx.ext.  This function is called by start_streaming() and stream_n_values() when saving is enabled. 

        Args:
            saving_filename (str): Root filename

        Returns:
            str: Generated filename
        """

        filename_wo_ext, filename_ext = os.path.splitext(saving_filename)
        # files that follow naming convention, returns list of varname_filename (no __idx.ext)
        matching_files = [os.path.splitext(file)[0].split(
            "__")[0] for file in glob.glob(os.path.join(saving_dir, f"*{filename_wo_ext}*{filename_ext}"))]

        if not matching_files:
            return os.path.join(saving_dir, saving_filename)

        # counts files with the same varname_filename
        idx = max([matching_files.count(item) for item in set(matching_files)])

        return os.path.join(saving_dir, f"{filename_wo_ext}__{idx}{filename_ext}")

    async def _async_remove_item_from_list(self, _list, task):
        """ Removes a task from a list of tasks asynchronously. This function is called by _save_data_to_file() when a task is finished.

        Args:
            _list (list):  A list of tasks
            task (asyncio task): The task to be removed from _list
        """
        _list.remove(task)

    def _check_periods(self, periods, variables):
        """Checks the periods format and values. If periods is an int, it is converted to a list of the same length as variables. If periods is an empty list, it is converted to a list of 1000s. If periods is a list, it is checked that it has the same length as variables and that all values are integers.

        Args:
            periods (_type_): variable periods passed as an argument to a monitoring function
            variables (list): list of variables

        Returns:
            periods (list of ints): Sanity checked periods
        """

        if isinstance(periods, int):
            periods = [periods]*len(variables)
        elif periods == []:
            _print_warning("No periods passed, using default value of 1000")
            periods = [1000]*len(variables)

        for period in periods:
            if period < 500 and period > 1:
                warnings.warn(
                    "Periods < 500 will send messages too frequently and may cause the websocket to crash. Use streaming methods instead.")

        assert len(periods) == len(
            variables), "Periods list must have the same length as variables list"
        for p in periods:
            assert isinstance(
                p, int), "Periods must be integers"

        return periods
