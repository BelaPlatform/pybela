import asyncio
import nest_asyncio
import websockets
import json
import errno
import struct
import os
from .utils import _print_error, _print_warning, _print_ok


class Watcher:

    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Watcher class

            Args:
                ip (str, optional): Remote address IP. If using internet over USB, the IP won't work, pass "bela.local". Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """

        self.project_name = None
        self._sample_rate = None

        self.ip = ip
        self.port = port
        self.data_add = data_add
        self.control_add = control_add
        self.ws_ctrl_add = f"ws://{self.ip}:{self.port}/{self.control_add}"
        self.ws_data_add = f"ws://{self.ip}:{self.port}/{self.data_add}"
        self.ws_ctrl = None
        self.ws_data = None

        self._list_response_queue = asyncio.Queue()

        # receive data message queue
        self._received_data_msg_queue = asyncio.Queue()
        self._process_received_data_msg_worker_task = None

        # send data message queue
        self._to_send_data_msg_queue = asyncio.Queue()
        self._sending_data_msg_worker_task = None

        self._watcher_vars = None

        self._mode = "WATCH"

        global _pybela_ws_register
        try:
            _ = _pybela_ws_register
        except NameError:  # initialise _pybela_ws_register only once in runtime
            _pybela_ws_register = {"WATCH": {},
                                   "STREAM":  {},
                                   "LOG":  {},
                                   "MONITOR":  {},
                                   "CONTROL":  {}}

        self._pybela_ws_register = _pybela_ws_register

        # debug
        self._printall_responses = False

        # event loop needs to be nested - otherwise it conflicts with jupyter's event loop
        nest_asyncio.apply()

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def watcher_vars(self):
        """Returns variables in watcher with their properties (name, type, timestamp_mode, log_filename, data_length)

        Returns:
            list of dicts: List of variables in watcher and their properties
        """
        if self._watcher_vars == None:  # populate
            _list = self.list()
            self._watcher_vars = self._filtered_watcher_vars(
                _list["watchers"], lambda var: True)
        return self._watcher_vars   # updates every time start is called

    @property
    def watched_vars(self):
        """Returns a list of the variables in the watcher that are being watched (i.e., whose data is being sent over websockets for streaming or monitoring)

        Returns:
            list of str: List of watched variables
        """
        _list = self.list()
        return self._filtered_watcher_vars(_list["watchers"], lambda var: var["watched"])

    @property
    def unwatched_vars(self):
        """Returns a list of the variables in the watcher that are not being watched (i.e., whose data is NOT being sent over websockets for streaming or monitoring)

        Returns:
            list of str: List of unwatched variables
        """
        _list = self.list()
        return self._filtered_watcher_vars(_list["watchers"], lambda var: not var["watched"])

    # --- public methods --- #

    def connect(self):
        """Attempts to establish a WebSocket connection and prints a message indicating success or failure.

        """
        if self.is_connected():
            return "Already connected"

        async def _async_connect():
            try:
                # Close any open ctrl websocket open for the same mode (STREAM, LOG, MONITOR, WATCH)
                if self._pybela_ws_register[self._mode].get(self.ws_ctrl_add) is not None and self._pybela_ws_register[self._mode][self.ws_ctrl_add].open:
                    _print_warning(
                        f"pybela doesn't support more than one active connection at a time for a given mode. Closing previous connection for {self._mode} at {self.ws_ctrl_add}.")
                    await self._pybela_ws_register[self._mode][self.ws_ctrl_add].close()

                # Control and monitor can't be used at the same time
                if (self._mode == "MONITOR" and self._pybela_ws_register["CONTROL"].get(self.ws_ctrl_add) is not None and self._pybela_ws_register["CONTROL"][self.ws_ctrl_add].open) or (self._mode == "CONTROL" and self._pybela_ws_register["MONITOR"].get(self.ws_ctrl_add) is not None and self._pybela_ws_register["MONITOR"][self.ws_ctrl_add].open):
                    _print_warning(
                        f"pybela doesn't support running control and monitor modes at the same time. You are currently running {'CONTROL' if self._mode=='MONITOR' else 'MONITOR'} at {self.ws_ctrl_add}. You can close it running controller.disconnect()")
                    _print_error("Connection failed")
                    return 0

                # Connect to the control websocket
                self.ws_ctrl = await websockets.connect(self.ws_ctrl_add)
                self._pybela_ws_register[self._mode][self.ws_ctrl_add] = self.ws_ctrl

                # Check if the response indicates a successful connection
                response = json.loads(await self.ws_ctrl.recv())
                if "event" in response and response["event"] == "connection":
                    self.project_name = response["projectName"]
                    # Send connection reply to establish the connection
                    self.send_ctrl_msg({"event": "connection-reply"})

                    # Connect to the data websocket
                    self.ws_data = await websockets.connect(self.ws_data_add)
                    self._process_received_data_msg_worker_task = asyncio.create_task(
                        self._process_data_msg_worker())
                    self._sending_data_msg_worker_task = asyncio.create_task(
                        self._send_data_msg_worker())

                    # Start listener loops
                    self._start_listener(self.ws_ctrl, self.ws_ctrl_add)
                    self._start_listener(self.ws_data, self.ws_data_add)

                    # refresh watcher vars in case new project has been loaded in Bela
                    self._list = self.list()
                    self._sample_rate = self._list["sampleRate"]
                    self._watcher_vars = self._filtered_watcher_vars(self._list["watchers"],
                                                                     lambda var: True)
                    _print_ok("Connection successful")
                    return 1
                else:
                    _print_error("Connection failed")
                    return 0
            except Exception as e:
                raise ConnectionError(f"Connection failed: {str(e)}.")

        return asyncio.run(_async_connect())

    def stop(self):
        """Closes websockets
        """
        async def _async_stop():
            if self.ws_ctrl is not None and self.ws_ctrl.open:
                await self.ws_ctrl.close()
            if self.ws_data is not None and self.ws_data.open:
                await self.ws_data.close()
            if self._process_received_data_msg_worker_task is not None:
                self._process_received_data_msg_worker_task.cancel()
            if self._sending_data_msg_worker_task is not None:
                self._sending_data_msg_worker_task.cancel()
        return asyncio.run(_async_stop())

    def is_connected(self):
        return True if (self.ws_ctrl is not None and self.ws_ctrl.open) and (self.ws_data is not None and self.ws_data.open) else False

    def list(self):
        """ Asks the watcher for the list of variables and their properties and returns it
        """
        async def _async_list():
            self.send_ctrl_msg({"watcher": [{"cmd": "list"}]})
            # Wait for the list response to be available

            list_res = await self._list_response_queue.get()
            self._list_response_queue.task_done()
            return list_res

        return asyncio.run(_async_list())

    def send_ctrl_msg(self, msg):
        """Send control message

        Args:
            msg (str): Message to send to the Bela watcher. Example: {"watcher": [{"cmd": "list"}]}
        """
        self._send_msg(self.ws_ctrl_add, json.dumps(msg))

    # --- private methods --- #

    # start listener

    def _start_listener(self, ws, ws_address):
        """Start listener for messages. The listener is a while True loop that runs in the background and processes messages received in ws as they are received.

        Args:
            ws (websocket): Websocket object
            ws_address (str): Websocket address
        """
        async def _async_start_listener(ws, ws_address):
            try:
                while ws is not None and ws.open:
                    msg = await ws.recv()
                    if self._printall_responses:
                        print(msg)
                    if ws_address == self.ws_data_add:
                        self._received_data_msg_queue.put_nowait(msg)
                    elif ws_address == self.ws_ctrl_add:
                        self._process_ctrl_msg(msg)
                    else:
                        print(msg)
            except Exception as e:
                if ws.open:  # otherwise websocket was closed intentionally
                    _handle_connection_exception(
                        ws_address, e, "receiving message")
        asyncio.create_task(
            _async_start_listener(ws, ws_address))

    # send message

    def _send_msg(self, ws_address, msg):
        """Send message to websocket

        Args:
            ws_address (str): Websocket address
            msg (str): Message to send
        """
        async def _async_send_msg(ws_address, msg):
            try:
                if ws_address == self.ws_data_add and self.ws_data is not None and self.ws_data.open:
                    asyncio.create_task(self._to_send_data_msg_queue.put(msg))
                elif ws_address == self.ws_ctrl_add and self.ws_ctrl is not None and self.ws_ctrl.open:
                    await self.ws_ctrl.send(msg)
            except Exception as e:
                _handle_connection_exception(ws_address, e, "sending message")
                return 0
        asyncio.run(_async_send_msg(ws_address, msg))

    # send messages

    async def _send_data_msg_worker(self):
        """ Send data message to websocket. Runs as long as websocket is open.
        """
        while self.ws_data is not None and self.ws_data.open:
            msg = await self._to_send_data_msg_queue.get()
            await self.ws_data.send(msg)
            self._to_send_data_msg_queue.task_done()

    # process messages

    async def _process_data_msg_worker(self):
        """Process data message. 

        Args:
            msg (str): Bytestring with data
        """

        while self.ws_data is not None and self.ws_data.open:
            msg = await self._received_data_msg_queue.get()
            await self._process_data_msg(msg)
            self._received_data_msg_queue.task_done()

    async def _process_data_msg(self, msg):
        """Process data message. This method is overwritten by the streamer.

        Args:
            msg (str): Bytestring with data
        """
        pass

    def _process_ctrl_msg(self, msg):
        """Process control message

        Args:
            msg (str): Control message to process
        """
        _msg = json.loads(msg)

        # response to list cmd
        if "watcher" in _msg.keys() and "sampleRate" in _msg["watcher"].keys():
            self._list_response_queue.put_nowait(_msg["watcher"])

    def _parse_binary_data(self, binary_data, timestamp_mode, _type):
        """Binary data parser. This method is used both by the streamer and the logger to parse the binary data buffers.

        Args:
            binary_data (bytestring): String of bytes to parse
            timestamp_mode (str): Timestamp mode ("sparse" or "dense")
            _type (str): Type of the variable ("f", "j", "i", "c", "d")

        Returns:
            dict: Dictionary with parsed buffer and timestamps
        """

        _type = 'i' if _type == 'j' else _type

        data_length = self.get_data_length(_type, timestamp_mode)
        # the format is the same for both logger and streamer so the parsing method is shared

        parsed_buffer = None
        if self._mode == "STREAM" or self._mode == "LOG":
            # sparse mode
            if timestamp_mode == "sparse":
                # ensure that the buffer is the correct size (remove padding)
                binary_data = binary_data[:struct.calcsize("Q") + data_length*struct.calcsize(
                    _type)+data_length*struct.calcsize("I")]

                ref_timestamp, *_buffer = struct.unpack('Q' + f"{_type}" * data_length
                                                        + 'I'*data_length, binary_data)
                data = _buffer[:data_length]
                # remove padding
                rel_timestamps = _buffer[data_length:][:data_length]

                parsed_buffer = {"ref_timestamp": ref_timestamp,
                                 "data": data, "rel_timestamps": rel_timestamps}

            elif timestamp_mode == "dense":
                # ensure that the buffer is the correct size
                # binary_data = binary_data[:struct.calcsize(
                #     'Q')+data_length*struct.calcsize(_type)]

                ref_timestamp, * \
                    data = struct.unpack(
                        'Q' + f"{_type}"*int((len(binary_data) - struct.calcsize('Q'))/struct.calcsize(_type)), binary_data)

                parsed_buffer = {
                    "ref_timestamp": ref_timestamp, "data": data}

        elif self._mode == "MONITOR":
            ref_timestamp, *_buffer = struct.unpack('Q' + f"{_type}" * int(
                (len(binary_data) - struct.calcsize("Q")) // struct.calcsize(_type)), binary_data)
            # size of the buffer is not fixed as in the other modes

            parsed_buffer = {
                "timestamp": ref_timestamp, "value": _buffer[0]}

        return parsed_buffer

    # --- utils --- #

    def get_latest_timestamp(self):
        return self.list()["timestamp"]

    async def _async_remove_item_from_list(self, _list, task):
        """Remove item from list. Used to remove listeners from the list of listeners.

        Args:
            _list (list): list of tasks
            task (asyncio.Task): task to be removed
        """
        _list.remove(task)

    def _filtered_watcher_vars(self, watchers, filter_func):
        """Filter variables in watcher depending on condition given by filter_func

        Args:
            watchers (list of dicts): List of variables in watcher and their properties
            filter_func (function): filter function

        Returns:
            dict: Filtered variables
        """
        return [{
            "name": var["name"],
            "type": var["type"],
            "timestamp_mode": "sparse" if var["timestampMode"] == 1 else "dense" if var["timestampMode"] == 0 else None,
            # "log_filename": var["logFileName"], # this is updated every time log is called so better not to store it
            "data_length": self.get_data_length(var["type"], "sparse" if var["timestampMode"] == 1 else "dense" if var["timestampMode"] == 0 else None,),
            "monitor": var["monitor"]
        }
            for var in watchers if filter_func(var)]

    def _var_arg_checker(self, variables):
        """ Checks if variables passed to a function are passed as names in a list. It also checks if the variables requested are in the watcher. If none are passed, returns all variables in watcher.

        Args:
            variables (list of str): Variables arg passed to a function
        """

        if len(variables) == 0:
            # if no variables are specified, return all watcher variables (default)
            return [var["name"] for var in self.watcher_vars]

        variables = variables if isinstance(variables, list) else [
            variables]  # variables should be a list of strings

        # check if variables are in watcher
        for var in variables:
            if var not in [v["name"] for v in self.watcher_vars]:
                raise ValueError(
                    f"Variable {var} is not in the watcher. Please check the list of variables in the watcher with watcher.list().")

        return variables

    def _generate_local_filename(self, local_path):
        # if file already exists, throw a warning and add number at the end of the filename
        new_local_path = local_path  # default
        if os.path.exists(local_path):
            base, ext = os.path.splitext(local_path)
            counter = 1
            new_local_path = local_path
            while os.path.exists(new_local_path):
                new_local_path = f"{base}_{counter}{ext}"
                counter += 1
            _print_warning(
                f"{local_path} already exists. Renaming file to {new_local_path}")

        return new_local_path

    def get_prop_of_var(self, var_name, prop):
        """Get property of variable. Properties: name, type, timestamp_mode, log_filename, data_length

        Args:
            var_name (str): Variable name
            prop (str): Requested property

        Returns:
            (type depending on prop): Requested property
        """
        return next(
            (v[prop] for v in self.watcher_vars if v['name'] == var_name), None)

    def get_data_byte_size(self, var_type):
        """Returns the byte size of the data type

        Args:
            var_type (str): Variable type

        Returns:
            int: byte size of the variable type 
        """
        data_byte_size_map = {
            "f": 4,
            "j": 4,
            "i": 4,
            "c": 8,
            "d": 8,
        }
        return data_byte_size_map.get(var_type, 0)

    def get_data_length(self, var_type, timestamp_mode):
        """Data length in the buffer

        Args:
            var_type (str): Variable type
            timestamp_mode (str): Timestamp mode

        Returns:
            int: Data length in the buffer (number of elements) 
        """
        dense_map = {
            "f": 1024,
            "j": 1024,
            "i": 1024,
            "c": 512,
            "d": 512,
        }
        sparse_map = {
            "f": 512,
            "j": 512,
            "i": 512,
            "c": 341,
            "d": 341,
        }
        if timestamp_mode == "dense":
            return dense_map.get(var_type, 0)
        if timestamp_mode == "sparse":
            return sparse_map.get(var_type, 0)

        else:
            # return error message
            return 0

    def get_buffer_size(self, var_type, timestamp_mode):
        """Returns the buffer size in bytes for buffers stored in a log file. This is the size of the buffer that is sent over websockets.

        Args:
            var_type (str): Variable type
            timestamp_mode (str): Timestamp mode

        Returns:
            int: Buffer size in bytes
        """
        # for logging
        data_length = self.get_data_length(var_type, timestamp_mode)
        if timestamp_mode == "sparse":
            if self.get_data_byte_size(var_type) == 4:
                return struct.calcsize('Q')+data_length*struct.calcsize(var_type)+data_length*struct.calcsize("I")
            elif self.get_data_byte_size(var_type) == 8:
                return struct.calcsize('Q')+data_length*struct.calcsize(var_type)+data_length*struct.calcsize("I")+4
        elif timestamp_mode == "dense":
            return struct.calcsize('Q')+data_length*struct.calcsize(var_type)
        else:
            # return error message
            return 0

    # destructor

    def __del__(self):
        self.stop()  # stop websockets


def _handle_connection_exception(ws_address, exception, action):
    bela_msg = "Make sure Bela is connected to the same network as your computer, that the IP address is correct, and that there is a project running on Bela."
    _print_error(
        f"WebSocket exception while connecting to {ws_address}: {exception}.  {bela_msg}")
    if isinstance(exception, OSError):
        if exception.errno == errno.ECONNREFUSED:
            raise ConnectionError(
                f"Error {exception.errno}: Connection refused while connecting to {ws_address}. {bela_msg}")
        elif exception.errno == errno.ENETUNREACH:
            raise ConnectionError(
                f"Error {exception.errno}: Network is unreachable while connecting to {ws_address}.  {bela_msg}")
        else:
            raise ConnectionError(
                f"Error {exception.errno} while connecting to {ws_address}.  {bela_msg}")
    else:
        _print_error(f"Error while {action}: {exception}.  {bela_msg}")
