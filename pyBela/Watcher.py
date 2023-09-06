import asyncio
import nest_asyncio
import websockets
import json
import errno
import struct


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

        self.ip = ip
        self.port = port
        self.data_add = data_add
        self.control_add = control_add
        self.ws_ctrl_add = f"ws://{self.ip}:{self.port}/{self.control_add}"
        self.ws_data_add = f"ws://{self.ip}:{self.port}/{self.data_add}"

        self.ws_ctrl = None
        self.ws_data = None

        self._ctrl_listener = None
        self._data_listener = None

        self._watcher_vars = None
        self._list_response_available = asyncio.Event()
        self._list_response = None

        # debug
        self._printall_responses = False

        # event loop needs to be nested - otherwise it conflicts with jupyter's event loop
        nest_asyncio.apply()

    @property
    def watcher_vars(self):
        """Returns variables in watcher with their properties (name, type, timestamp_mode, log_filename, data_length)

        Returns:
            list of dicts: List of variables in watcher and their properties
        """
        if self._watcher_vars == None:  # populate
            self._watcher_vars = self._filtered_vars(lambda var: True)
        return self._watcher_vars   # updates every time start is called

    @property
    def watched_vars(self):
        """Returns a list of the variables in the watcher that are being watched (i.e., whose data is being sent over websockets for streaming or monitoring)

        Returns:
            list of str: List of watched variables
        """
        return self._filtered_vars(lambda var: var["watched"])

    @property
    def unwatched_vars(self):
        """Returns a list of the variables in the watcher that are not being watched (i.e., whose data is NOT being sent over websockets for streaming or monitoring)

        Returns:
            list of str: List of unwatched variables
        """
        return self._filtered_vars(lambda var: not var["watched"])

    # --- public methods --- #

    def start(self):
        """Starts the websockets connection and listeners
        """
        if self._ctrl_listener is None:  # avoid duplicate listeners
            self.start_ctrl_listener()
        if self._data_listener is None:
            self.start_data_listener()

        # refresh watcher vars in case new project has been loaded in Bela
        self._watcher_vars = self._filtered_vars(lambda var: True)

    def stop(self):
        """Stops listeners and closes websockets
        """
        async def async_stop():
            if self._ctrl_listener is not None:
                self._ctrl_listener.cancel()
                if self.ws_ctrl is not None:
                    await self.ws_ctrl.close()
                self._ctrl_listener = None  # empty the listener
            if self._data_listener is not None:
                self._data_listener.cancel()
                if self.ws_data is not None:
                    await self.ws_data.close()
                self._data_listener = None

        return asyncio.run(async_stop())

    def list(self):
        """ Asks the watcher for the list of variables and their properties and returns it
        """
        async def async_list():
            if self._ctrl_listener is None:  # start listener if listener is not running
                self.start_ctrl_listener()
            self.send_ctrl_msg({"watcher": [{"cmd": "list"}]})
            # Wait for the list response to be available
            await self._list_response_available.wait()
            self._list_response_available.clear()  # Reset the event for the next call
            return self._list_response

        return asyncio.run(async_list())

    def send_ctrl_msg(self, msg):
        """Send control message

        Args:
            msg (str): Message to send to the Bela watcher. Example: {"watcher": [{"cmd": "list"}]}
        """
        self._send_msg(self.ws_ctrl, self.ws_ctrl_add, msg)

    def start_ctrl_listener(self):
        """Start listener for control messages
        """
        self._ctrl_listener = self._start_listener(
            self.ws_ctrl, self.ws_ctrl_add)

    def start_data_listener(self):
        """Start listener for data messages
        """
        self._data_listener = self._start_listener(
            self.ws_data, self.ws_data_add)

    # --- private methods --- #

    # start listener

    def _start_listener(self, ws, ws_address):
        """Start listener for messages. This method is called by start_ctrl_listener and start_data_listener.

        Args:
            ws (websocket): Websocket object
            ws_address (str): Websocket address
        """
        async def _start_listener_callback(ws, ws_address):
            async def _rec_msg_callback(ws, ws_address):
                try:
                    async with websockets.connect(ws_address) as ws:
                        while True:
                            msg = await ws.recv()
                            if self._printall_responses:
                                print(msg)
                            if ws_address == self.ws_data_add:
                                self._process_data_msg(msg)
                            elif ws_address == self.ws_ctrl_add:
                                self._process_ctrl_msg(msg)
                            else:
                                print(msg)
                except Exception as e:
                    handle_connection_exception(
                        ws_address, e, "receiving message")
            await _rec_msg_callback(ws, ws_address)
        loop = asyncio.get_event_loop()
        # create_task() is needed so that the listener runs in the background and prints messages as received without blocking the cell
        listener_task = loop.create_task(
            _start_listener_callback(ws, ws_address))
        return listener_task

    # send message

    def _send_msg(self, ws, ws_address, msg):
        """Send message to websocket

        Args:
            ws (websocket): Websocket object
            ws_address (str): Websocket address
            msg (str): Message to send
        """
        async def _send_msg_callback(ws, ws_address, msg):
            try:
                # here you can use the same websocket for multiple messages -- but avoid using the same one for sending and receiving
                async with websockets.connect(ws_address) as ws:
                    await ws.send(json.dumps(msg))
            except Exception as e:
                handle_connection_exception(ws_address, e, "sending message")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_send_msg_callback(ws, ws_address, msg))

    # process messages

    def _process_data_msg(self, msg):  # method overwritten by streamer
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

        # list cmd
        if "watcher" in _msg.keys() and "watchers" in _msg["watcher"].keys():
            self._list_response = _msg["watcher"]["watchers"]
            self._list_response_available.set()

        # connection event
        # if "event" in _msg.keys() and _msg["event"] == "connection":
        #     print("Connection successful")  # FIXME this message is sent many times
        if "projectName" in _msg.keys():
            self.project_name = _msg["projectName"]

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

        else:  # dense mode
            # ensure that the buffer is the correct size
            binary_data = binary_data[:struct.calcsize(
                'Q')+data_length*struct.calcsize(_type)]

            ref_timestamp, * \
                data = struct.unpack('Q' + f"{_type}"*data_length, binary_data)

            parsed_buffer = {
                "ref_timestamp": ref_timestamp, "data": data}

        return parsed_buffer

     # --- utils --- #

    async def _async_remove_item_from_list(self, _list, task):
        """Remove item from list. Used to remove listeners from the list of listeners.

        Args:
            _list (list): list of tasks
            task (asyncio.Task): task to be removed
        """
        _list.remove(task)

    def _filtered_vars(self, filter_func):
        """Filter variables in watcher depending on condition given by filter_func

        Args:
            filter_func (function): filter function

        Returns:
            dict: Filtered variables
        """
        return [{
            "name": var["name"],
            "type": var["type"],
            "timestamp_mode":"sparse" if var["timestampMode"] == 1 else "dense" if var["timestampMode"] == 0 else None,
            "log_filename": var["logFileName"],
            "data_length": self.get_data_length(var["type"], "sparse" if var["timestampMode"] == 1 else "dense" if var["timestampMode"] == 0 else None,)
        }
            for var in self.list() if filter_func(var)]

    def get_prop_of_var(self, var_name, prop):
        # TODO replace get_data_length by this
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


def handle_connection_exception(ws_address, exception, action):
    if isinstance(exception, websockets.exceptions.WebSocketException):
        print(
            f"WebSocket exception while connecting to {ws_address}: {exception}")
    elif isinstance(exception, OSError):
        if exception.errno == errno.ECONNREFUSED:
            print(
                f"Error {exception.errno}: Connection refused while connecting to {ws_address}")
        elif exception.errno == errno.ENETUNREACH:
            print(
                f"Error {exception.errno}: Network is unreachable while connecting to {ws_address}")
        else:
            print(f"Error {exception.errno} while connecting to {ws_address}")
    else:
        print(f"Error while {action}: {exception}")
