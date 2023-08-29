import json
import copy
import os
import glob
import asyncio
import aiofiles  # async file i/o
from collections import deque  # circular buffers

import bokeh.plotting
import bokeh.io
import bokeh.driving
from bokeh.resources import INLINE


from .Watcher import Watcher


class Streamer(Watcher):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Streamer class

            Args:
                ip (str, optional): Remote address IP. Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """

        super(Streamer, self).__init__(ip, port, data_add, control_add)

        # number of streaming buffers (not of data points!)
        self._streaming_buffers_queue_length = 20
        self._streaming_buffers_queue = None
        self.last_streamed_buffer = {}  # FIXME populate at start

        self._streaming_mode = "OFF"  # OFF, FOREVER, N_FRAMES :: this flag prevents writing into the streaming buffer unless requested by the user using the start/stop_streaming() functions
        self._streaming_buffer_available = asyncio.Event()

        self._saving_enabled = False
        self._saving_filename = None
        self._saving_task = None
        self._active_saving_tasks = []
        self._saving_file_locks = {}

    # --- public methods --- #

    # - setters & getters

    @property
    def streaming_buffers_queue_length(self):
        """Returns the maximum number of streaming buffers allowed in self.streaming_buffers_queue"""
        return self._streaming_buffers_queue_length

    @streaming_buffers_queue_length.setter
    def streaming_buffers_queue_length(self, value):
        """Sets the maximum number of streaming buffers allowed in self.streaming_buffers_queue. Warning: setting the streaming buffer value will result in deleting the current streaming buffer queue.
        """
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

    def start(self):
        super(Streamer, self).start()
        self._streaming_buffers_queue = {var["name"]: deque(
            maxlen=self._streaming_buffers_queue_length) for var in self.watcher_vars}
        self.last_streamed_buffer = {
            var["name"]: {"data": [], "timestamps": []} for var in self.watcher_vars}

    @property
    def streaming_buffers_data(self):
        """Returns a dict where each key corresponds to a variable and each value to a flat list of the streamed values. Does not return timestamps of each datapoint since that depends on how often the variables are reassigned in the Bela code.
        Returns:
            dict: Dict of flat lists of streamed values.
        """
        data = {}
        for var in self.streaming_buffers_queue:
            data[var] = []
            for buffer in self.streaming_buffers_queue[var]:
                data[var].extend(buffer["data"])
        return data

    # - streaming methods

    # stream forever until stopped

    def start_streaming(self, variables=[], saving_enabled=False, saving_filename="var_stream.txt"):
        """
        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (_type_, optional) Filename for saving the streamed data. Defaults to None.
        """

        if self.is_streaming():
            self.stop_streaming()  # stop any previous streaming

        self.start()  # start before setting saving enabled to ensure streaming buffer is initialised properly

        self._saving_enabled = True if saving_enabled else False
        self._saving_filename = self._generate_filename(
            saving_filename) if saving_enabled else None

        if len(variables) == 0:
            # if no variables are specified, stream all watcher variables (default)
            variables = [var["name"] for var in self.watcher_vars]

        variables = variables if isinstance(variables, list) else [
            variables]  # variables should be a list of strings

        self._streaming_mode = "FOREVER"

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "watch", "watchers": variables}]})

    def stop_streaming(self, variables=[]):
        """
        Args:
            variables (list, optional): List of variables to stop streaming. Defaults to [].

        Returns:
            streaming_buffers_queue (dict): Dict containing the streaming buffers for each streamed variable.
        """
        return asyncio.run(self.async_stop_streaming(variables))

    async def async_stop_streaming(self, variables=[]):

        self.stop()
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

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "unwatch", "watchers": variables}]})

    def stream_n_frames(self, variables=[], n_frames=1000, delay=0, saving_enabled=False, saving_filename=None):
        """
        Note: This function will block the main thread until n_frames have been streamed. Since the streamed values come in blocks, the actual number of returned frames streamed may be higher than n_frames, unless n_frames is a multiple of the block size (streamer._streaming_block_size).

        To avoid blocking, use the async version of this function:
            stream_task = asyncio.create_task(streamer.async_stream_n_frames(variables, n_frames, saving_enabled, saving_filename))
        and retrieve the streaming buffer using:
             streaming_buffers_queue = await stream_task

        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            n_frames (int, optional): Number of frames to stream. Defaults to 1000.
            delay (int, optional): _description_. Defaults to 0.
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (_type_, optional) Filename for saving the streamed data. Defaults to None.

        Returns:
            streaming_buffers_queue (dict): Dict containing the streaming buffers for each streamed variable.
        """
        # blocks thread until n_frames are streamed -- to avoid blocking, use async version

        # TODO implement delay once data comes timestamped
        return asyncio.run(self.async_stream_n_frames(variables, n_frames, delay, saving_enabled, saving_filename))

    async def async_stream_n_frames(self, variables=[], n_frames=1000, delay=None, saving_enabled=False, saving_filename="var_stream.txt"):
        """ Asynchronous version of stream_n_frames(). Usage: 
            stream_task = asyncio.create_task(streamer.async_stream_n_frames(variables, n_frames, saving_enabled, saving_filename))
        and retrieve the streaming buffer using:
             streaming_buffers_queue = await stream_task


        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            n_frames (int, optional): Number of frames to stream. Defaults to 1000.
            delay (int, optional): _description_. Defaults to 0.
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (_type_, optional) Filename for saving the streamed data. Defaults to None.

        Returns:
            _type_: _description_
        """
        # resizes the streaming buffer size to n_frames and returns it when full

        # start watcher and populate watcher vars
        if self.is_streaming():
            self.stop_streaming()  # stop any previous streaming

        self.start()

        if len(variables) == 0:
            # if no variables are specified, stream all watched variables
            variables = [var["name"] for var in self.watcher_vars]

        variables = variables if isinstance(variables, list) else [
            variables]  # variables should be a list of strings

        # variables might have different buffer sizes -- the code below finds the minimum number of buffers needed to stream n_frames for all variables
        buffer_sizes = [
            self.get_data_length(var["type"], var["timestamp_mode"])
            for var in self.watcher_vars if var["name"] in variables]

        # TODO add a warning when there's different buffer sizes ?

        # ceiling division
        n_buffers = -(-n_frames // min(buffer_sizes))

        # using setter to automatically resize buffer
        self.streaming_buffers_queue_length = n_buffers

        self._saving_enabled = True if saving_enabled else False
        self._saving_filename = self._generate_filename(
            saving_filename) if saving_enabled else None

        self._streaming_mode = "N_FRAMES"  # flag cleared in __rec_msg_callback

        # watch only the variables specified
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "unwatch", "watchers": [var["name"] for var in self.watcher_vars]}, {"cmd": "watch", "watchers": variables}]})

        # await until streaming buffer is full
        await self._streaming_buffer_available.wait()
        self._streaming_buffer_available.clear()

        # turns off listener, unwatches variables
        self.stop_streaming(variables)

        return self.streaming_buffers_queue

    # - utils

    def is_streaming(self):
        return True if self._streaming_mode != "OFF" else False

    def load_data_from_file(self, filename):
        """
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
            print(f"Error while loading data from file: {e}")
            return None

        return data

    # - plotting

    def _data_plot(self,
                   data,
                   x_var,
                   y_vars,
                   y_range=None,
                   rollover=None,
                   plot_update_delay=90):
        """Return a function defining a Bokeh app for streaming. A maximum of `rollover`
        data points are shown at a time.
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

            # Create line glyphs for each y_var
            for y_var in y_vars:
                p.circle(source=source, x="timestamps",
                         y=y_var, legend_label=y_var, size=1)

            @bokeh.driving.linear()
            def update(step):
                # Update plot by streaming in data
                new_data = {"timestamps": data[x_var]["timestamps"]}
                for y_var in y_vars:
                    new_data[y_var] = data[y_var]["data"]
                source.stream(new_data, rollover)

            doc.add_root(p)
            doc.add_periodic_callback(update, plot_update_delay)
        return _app

    def plot_data(self, x_var, y_vars, y_range=None, plot_update_delay=100, rollover=1000):
        bokeh.io.output_notebook(INLINE)
        bokeh.io.show(self._data_plot(data=self.last_streamed_buffer, x_var=x_var,
                      y_vars=y_vars, y_range=y_range, plot_update_delay=plot_update_delay, rollover=rollover))

    # --- private methods --- #

    def _process_data_msg(self, msg):
        global _channel, _type
        try:
            _, __ = _channel, _type
        except NameError:  # initialise global variables to None
            _channel = None
            _type = None

        # in case buffer is received whilst streaming mode is on but parsed after streaming_enabled has changed
        _saving_enabled = copy.copy(self._saving_enabled)
        if self._streaming_mode != "OFF":
            if len(msg) == 3:
                # parse buffer header
                _channel = int(str(msg)[2])
                _type = str(msg)[4]

                assert _type in ['i', 'f', 'j', 'd',
                                 'c'], f"Unsupported type: {_type}"

                assert _type == self._watcher_vars[_channel][
                    'type'], f"Type mismatch: {_type} != {self._watcher_vars[_channel]['type']}"

                # convert unsigned int to int -- struct does not support unsigned ints
                _type = 'i' if _type == 'j' else _type

            elif len(msg) > 3 and _channel is not None and _type is not None:
                # parse buffer body
                parsed_buffer = self._parse_binary_data(
                    msg, self._watcher_vars[_channel]["timestamp_mode"], _type)

                # append message to the streaming buffers queue
                self._streaming_buffers_queue[self._watcher_vars[_channel]['name']].append(
                    parsed_buffer)
                # needed for streaming plots
                self.last_streamed_buffer[self._watcher_vars[_channel]
                                          ['name']]["data"] = parsed_buffer["data"]
                if self._watcher_vars[_channel]["timestamp_mode"] == "dense":
                    self.last_streamed_buffer[self._watcher_vars[_channel]
                                              ['name']]["timestamps"] = [parsed_buffer["ref_timestamp"] + i for i in range(0, len(parsed_buffer["data"]))]
                elif self._watcher_vars[_channel]["timestamp_mode"] == "sparse":  # sparse
                    self.last_streamed_buffer[self._watcher_vars[_channel]["name"]]["timestamps"] = [
                        parsed_buffer["ref_timestamp"] + i for i in parsed_buffer["rel_timestamps"]]

                if _saving_enabled:
                    _saving_var_filename = f"{self._watcher_vars[_channel]['name']}_{self._saving_filename}"
                    # save the data asynchronously
                    saving_task = asyncio.create_task(
                        self._save_data_to_file(_saving_var_filename, parsed_buffer))
                    self._active_saving_tasks.append(saving_task)

                # if streaming buffers queue is full for watched variables and streaming mode is N_FRAMES
                if self._streaming_mode == "N_FRAMES" and all(len(self._streaming_buffers_queue[var["name"]]) == self._streaming_buffers_queue_length for var in self.watched_vars):
                    self._streaming_mode = "OFF"
                    self._streaming_buffer_available.set()

    async def _save_data_to_file(self, filename, msg):
        try:
            # make sure there are not two processes writing to the same file
            if filename not in self._saving_file_locks.keys():
                # create lock for file if it does not exist
                self._saving_file_locks[filename] = asyncio.Lock()

            async with self._saving_file_locks[filename]:
                async with aiofiles.open(filename, "a") as f:
                    _json = json.dumps(copy.copy(msg))
                    await f.write(_json+"\n")

        except Exception as e:
            print(f"Error while saving data to file: {e}")

        finally:
            await self._async_remove_item_from_list(self._active_saving_tasks, asyncio.current_task())

    def _generate_filename(self, saving_filename):
        # adds a number to the end of the filename if it already exists to avoid overwriting saved data files
        # naming convention is varname_filename__idx.ext

        filename_wo_ext, filename_ext = os.path.splitext(saving_filename)
        # files that follow naming convention, returns list of varname_filename (no __idx.ext)
        matching_files = [os.path.splitext(file)[0].split(
            "__")[0] for file in glob.glob(f"*{filename_wo_ext}*{filename_ext}")]

        if not matching_files:
            return saving_filename

        # counts files with the same varname_filename
        idx = max([matching_files.count(item) for item in set(matching_files)])

        return f"{filename_wo_ext}__{idx}{filename_ext}"

    async def _async_remove_item_from_list(self, _list, task):
        _list.remove(task)
