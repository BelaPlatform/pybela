import asyncio
import array
import aiofiles  # async file i/o
import json
import copy
from collections import deque  # circular buffers
from .Watcher import Watcher


class Streamer(Watcher):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Streamer class __summary__.

            Args:
                ip (str, optional): Remote address IP. Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """

        super(Streamer, self).__init__(ip, port, data_add, control_add)

        self._streaming_buffer_size = 1000
        self._streaming_buffer = None
        self._streaming_mode = None  # OFF, FOREVER, N_FRAMES :: this flag prevents writing into the streaming buffer unless requested by the user using the start/stop_streaming() functions
        self._streaming_buffer_available = asyncio.Event()

        self._saving_enabled = False
        self._saving_filename = None
        self._saving_task = None
        self._active_saving_tasks = []

        self._file_locks = {}

    # setters & getters

    @property
    def streaming_buffer_size(self):
        return self._streaming_buffer_size

    @streaming_buffer_size.setter
    def streaming_buffer_size(self, value):
        self._streaming_buffer_size = value
        self._streaming_buffer = {var: deque(
            maxlen=self._streaming_buffer_size) for var in self.watcher_vars}  # resize streaming buffer

    @property
    def streaming_buffer(self):
        # convert dict of deque to dict of list
        return {key: list(value) for key, value in self._streaming_buffer.items()}

    def start(self):
        super(Streamer, self).start()
        self._streaming_buffer = {var: deque(
            maxlen=self._streaming_buffer_size) for var in self.watcher_vars}

    # --- public methods

    # stream forever until stopped
    def start_streaming(self, variables=[], saving_enabled=False, saving_filename=None):
        """_summary_

        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (_type_, optional) Filename for saving the streamed data. Defaults to None.
        """
        self._saving_enabled = True if saving_enabled else False
        self._saving_filename = "streamed_data.pkl" if saving_filename is None and saving_enabled else saving_filename
        # if no variables are specified, stream all watched variables
        if len(variables) == 0:
            variables = self.watcher_vars
        variables = variables if isinstance(variables, list) else [variables]

        self._streaming_mode = "FOREVER"
        self.start()
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "watch", "watchers": variables}]})

    def stop_streaming(self, variables=[]):
        """_summary_

        Args:
            variables (list, optional): List of variables to stop streaming. Defaults to [].

        Returns:
            streaming_buffer (dict): Dict containing the streaming buffers for each streamed variable.
        """
        return asyncio.run(self.async_stop_streaming(variables))

    async def async_stop_streaming(self, variables=[]):
        self.stop()
        self._streaming_mode = "OFF"

        if self._saving_enabled:
            self._saving_enabled = False
            self._saving_filename = None
            await asyncio.gather(*self._active_saving_tasks, return_exceptions=True)
            self._active_saving_tasks.clear()  # await all saving tasks

        if variables == []:
            variables = self.watched_vars  # stop streaming all watcher variables
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "unwatch", "watchers": variables}]})

        return self.streaming_buffer

    async def async_stream_n_frames(self, variables, n_frames, saving_enabled=False, saving_filename=None):
        # resizes the streaming buffer size to n_frames and returns it when full
        self._saving_enabled = True if saving_enabled else False
        self._saving_filename = "streamed_data.pkl" if saving_filename is None and saving_enabled else saving_filename

        # if no variables are specified, stream all watched variables
        if len(variables) == 0:
            variables = self.watcher_vars
        variables = variables if isinstance(variables, list) else [variables]

        self.start()
        self._streaming_mode = "N_FRAMES"  # flag cleared in __rec_msg_callback
        # using setter to automatically resize buffer
        self.streaming_buffer_size = n_frames

        # unwatch all variables
        self.send_ctrl_msg({"cmd": "unwatch", "watchers": self.watched_vars})
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "watch", "watchers": variables}]})  # watch only the variables specified

        # return when finished filling buffer
        await self._streaming_buffer_available.wait()
        self._streaming_buffer_available.clear()

        # turns off listener, unwatches variables
        self.stop_streaming(variables)

        return self.streaming_buffer

    def stream_n_frames(self, variables=[], n_frames=1000, delay=0, saving_enabled=False, filename=None):
        """_summary_

        Args:
            variables (list, optional): List of variables to be streamed. Defaults to [].
            n_frames (int, optional): Number of frames to stream. Defaults to 1000.
            delay (int, optional): _description_. Defaults to 0.
            saving_enabled (bool, optional): Enables/disables saving streamed data to local file. Defaults to False.
            saving_filename (_type_, optional) Filename for saving the streamed data. Defaults to None.

        Returns:
            streaming_buffer (dict): Dict containing the streaming buffers for each streamed variable.
        """
        # TODO implement delay once data comes timestamped
        return asyncio.run(self.async_stream_n_frames(variables, n_frames, saving_enabled, filename))

    def is_streaming(self):
        return True if self._streaming_mode != "OFF" else False

    def load_data_from_file(self, filename):
        try:
            data = []
            with open(filename, "r") as f:  # Open the file in binary read mode asynchronously
                while True:
                    line = f.readline()
                    if not line:
                        break
                    try:
                        # Load the next object from the file

                        data_list = json.loads(line)

                        data.extend(data_list)
                    except EOFError:
                        # Reached the end of the file
                        break
        except Exception as e:
            print(f"Error while loading data from file: {e}")
            return None

        return data

    # --- private methods

    def _parse_data_message(self, msg):
        global _type, _channel
        if self._streaming_mode != "OFF":
            if len(msg) == 3:
                _channel = int(str(msg)[2])
                _type = str(msg)[4]
            elif len(msg) > 3:
                _msg = array.array(_type, msg).tolist()
                self._streaming_buffer[self._watcher_vars[_channel]].extend(
                    _msg)  # FIXME this does not truncate once buffer size is reached
                if self._saving_enabled:
                    # avoid racing conditions # FIXME do everything in binary here?
                    _save_msg = copy.copy(_msg)
                    # Save the data asynchronously
                    saving_task = asyncio.create_task(self._save_data_to_file(
                        f"{self._watcher_vars[_channel]}_{self._saving_filename}", _save_msg))
                    self._active_saving_tasks.append(saving_task)

                if self._streaming_mode == "N_FRAMES" and all(len(self._streaming_buffer[var]) == self._streaming_buffer_size for var in self._watcher_vars):
                    self._streaming_mode = "OFF"
                    self._streaming_buffer_available.set()

    async def _save_data_to_file(self, filename, msg):
        # TODO warning if file already exists
        try:
            while self._saving_enabled:
                _msg = copy.copy(msg)

                if filename not in self._file_locks.keys():  # make sure there are not two processes writing to the same file
                    # create lock for file if it does not exist
                    self._file_locks[filename] = asyncio.Lock()
                async with self._file_locks[filename]:

                    # Open the file in binary append mode
                    async with aiofiles.open(filename, "a") as f:
                        _json = json.dumps(_msg)
                        await f.write(_json+"\n")
                        # Wait for a short interval before writing the next update
                # ensures data is not duplicated -- allows time for another message to arrive
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error while saving data to file: {e}")
