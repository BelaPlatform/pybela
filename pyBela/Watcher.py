import asyncio
import nest_asyncio
import websockets
import json
import errno


class Watcher:

    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Watcher class __summary__.

        Args:
            ip (str, optional): Remote address IP. Defaults to "192.168.7.2".
            port (int, optional): Remote address port. Defaults to 5555.
            data_add (str, optional): Data endpoint. Defaults to "gui_data".
            control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """

        self.project_name = None

        self.ip = ip
        self.port = port
        self.data_add = data_add
        self.control_add = control_add
        self.ws_control_add = f"ws://{self.ip}:{self.port}/{self.control_add}"
        self.ws_data_add = f"ws://{self.ip}:{self.port}/{self.data_add}"

        self.ws_control = None
        self.ws_data = None

        self._ctrl_listener = None
        self._data_listener = None

        self._watcher_vars = None
        self._list_response_available = asyncio.Event()
        self._list_response = None

        # event loop needs to be nested - otherwise it conflicts with jupyter's event loop
        nest_asyncio.apply()

    @property
    def watcher_vars(self):
        if self._watcher_vars == None:  # populate
            self._watcher_vars = [{"name": var["name"],
                                   "type":var["type"]} for var in self.list()]
        return self._watcher_vars   # updates every time start is called

    @property
    def watched_vars(self):
        return [{"name": var["name"], "type":var["type"]} for var in self.list() if var["watched"]]

    @property
    def unwatched_vars(self):
        return [{"name": var["name"], "type":var["type"]} for var in self.list() if var["unwatched"]]

    # public methods

    def start(self):
        if self._ctrl_listener is None:  # avoid duplicate listeners
            self.start_ctrl_listener()
        if self._data_listener is None:
            self.start_data_listener()

        # refresh watcher vars in case new project has been loaded in Bela
        self._watcher_vars = [{"name": var["name"],
                               "type":var["type"]} for var in self.list()]

    async def async_stop(self):
        if self._ctrl_listener is not None:
            self._ctrl_listener.cancel()
            if self.ws_control is not None:
                await self.ws_control.close()
            self._ctrl_listener = None  # empty the listener
        if self._data_listener is not None:
            self._data_listener.cancel()
            if self.ws_data is not None:
                await self.ws_data.close()
            self._data_listener = None

    def stop(self):
        return asyncio.run(self.async_stop())

    def list(self):
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
        self._send_msg(self.ws_control, self.ws_control_add, msg)

    def start_ctrl_listener(self):
        self._ctrl_listener = self._start_listener(
            self.ws_control, self.ws_control_add)

    def start_data_listener(self):
        self._data_listener = self._start_listener(
            self.ws_data, self.ws_data_add)

    # _private methods

    # start listener

    def _start_listener(self, ws, ws_address):
        loop = asyncio.get_event_loop()
        # create_task() is needed so that the listener runs in the background and prints messages as received without blocking the cell
        listener_task = loop.create_task(
            self._start_listener_callback(ws, ws_address))
        return listener_task

    async def _start_listener_callback(self, ws, ws_address):
        await self._rec_msg_callback(ws, ws_address)

    # send message

    def _send_msg(self, ws, ws_address, msg):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._send_msg_callback(ws, ws_address, msg))

    async def _send_msg_callback(self, ws, ws_address, msg):
        try:
            # here you can use the same websocket for multiple messages -- but avoid using the same one for sending and receiving
            async with websockets.connect(ws_address) as ws:
                await ws.send(json.dumps(msg))
        except Exception as e:
            handle_connection_exception(ws_address, e, "sending message")

    # receive message

    async def _rec_msg_callback(self, ws, ws_address):
        try:
            async with websockets.connect(ws_address) as ws:
                while True:
                    msg = await ws.recv()
                    if ws_address == self.ws_data_add:
                        self._parse_data_message(msg)
                    elif ws_address == self.ws_control_add:
                        self._parse_control_message(msg)
                    else:
                        print(msg)
        except Exception as e:
            handle_connection_exception(ws_address, e, "receiving message")

    def _parse_data_message(self, msg):  # method overwritten by streamer
        pass

    def _parse_control_message(self, msg):
        _msg = json.loads(msg)

        # list cmd
        if "watcher" in _msg.keys() and "watchers" in _msg["watcher"].keys():
            self._list_response = _msg["watcher"]["watchers"]
            self._list_response_available.set()

        # connection event
        # if "event" in _msg.keys() and _msg["event"] == "connection":
        #     print("Connection successful")  # FIXME this message is sent many times
        if "projectName" in _msg.keys():
            self._project_name = _msg["projectName"]

    # utils
    def get_buffer_size(self, var_type):
        buffer_size_map = {
            "f": 1024,
            "j": 1024,
            "i": 1024,
            "c": 512,
            "d": 512,
        }
        return buffer_size_map.get(var_type, 0)
    
    def get_data_size(self, var_type):
        data_size_map = {
            "f": 4,
            "j": 4,
            "i": 4,
            "c": 8,
            "d": 8,
        }
        return data_size_map.get(var_type, 0)

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
