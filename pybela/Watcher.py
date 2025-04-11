import asyncio
import websockets
import json
import errno
import struct
import os
import nest_asyncio
import paramiko
from .utils import _print_error, _print_warning, _print_ok


class Watcher:

    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Watcher class - manages websockets and abstracts communication with the Bela watcher

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

        self.ssh_client = None
        self.sftp_client = None

        self._watcher_vars = None
        self._mode = "WATCH"

        global _pybela_ws_register
        try:
            _ = _pybela_ws_register
        except NameError:  # initialise _pybela_ws_register only once in runtime
            _pybela_ws_register = {"event-loop": None,
                                   "WATCH": {},
                                   "STREAM":  {},
                                   "LOG":  {},
                                   "MONITOR":  {},
                                   "CONTROL":  {}}

        self._pybela_ws_register = _pybela_ws_register

        # if running in jupyter notebook, enable nest_asyncio
        is_running_on_jupyter_notebook = False
        try:
            get_ipython().__class__.__name__
            is_running_on_jupyter_notebook = True
            nest_asyncio.apply()
            print("Running in Jupyter notebook. Enabling nest_asyncio.")
        except NameError:
            pass

        # background event loop
        # If no loop exists, create a new one
        if self._pybela_ws_register["event-loop"] is None:

            if is_running_on_jupyter_notebook:
                self.loop = asyncio.get_event_loop()
            else:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
            self._pybela_ws_register["event-loop"] = self.loop
        else:  # if loop exists, use the existing one
            self.loop = self._pybela_ws_register["event-loop"]

        # tasks
        self._ctrl_listener_task = None
        self._data_listener_task = None
        self._process_received_data_msg_task = None
        self._send_data_msg_task = None
        self._send_ctrl_msg_task = None

        # queues
        self._received_data_msg_queue = asyncio.Queue()
        self._list_response_queue = asyncio.Queue()
        self._to_send_data_msg_queue = asyncio.Queue()
        self._to_send_ctrl_msg_queue = asyncio.Queue()

        # debug
        self._printall_responses = False

    # properties

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def watcher_vars(self):
        """Returns variables in watcher with their properties (name, type, timestamp_mode, log_filename, data_length). Can't be used in async functions, use _async_watcher_vars instead.

        Returns:
            list of dicts: List of variables in watcher and their properties
        """
        if self._watcher_vars == None:  # populate
            _list = self.list()
            self._watcher_vars = self._filtered_watcher_vars(
                _list["watchers"], lambda var: True)
        return self._watcher_vars   # updates every time start is called

    async def _async_watcher_vars(self):
        """Asynchronous version of watcher_vars

        Returns:
            list of dicts: List of variables in watcher and their properties
        """
        if self._watcher_vars == None:
            _list = await self._async_list()
            self._watcher_vars = self._filtered_watcher_vars(
                _list["watchers"], lambda var: True)
        return self._watcher_vars

    @property
    def watched_vars(self):
        """Returns a list of the variables in the watcher that are being watched (i.e., whose data is being sent over websockets for streaming or monitoring). Can't be used in async functions, use _async_watched_vars instead.

        Returns:
            list of str: List of watched variables
        """
        _list = self.list()
        return self._filtered_watcher_vars(_list["watchers"], lambda var: var["watched"])

    async def _async_watched_vars(self):
        """Async version of watched_vars

        Returns:
            list of str: List of watched variables
        """
        _list = await self._async_list()
        return self._filtered_watcher_vars(_list["watchers"], lambda var: var["watched"])

    @property
    def unwatched_vars(self):
        """Returns a list of the variables in the watcher that are not being watched (i.e., whose data is NOT being sent over websockets for streaming or monitoring). Can't be used in async functions, use _async_unwatched_vars instead.

        Returns:
            list of str: List of unwatched variables
        """
        _list = self.list()
        return self._filtered_watcher_vars(_list["watchers"], lambda var: not var["watched"])

    async def _async_unwatched_vars(self):
        """Async version of unwatched_vars

        Returns:
            list of str: List of unwatched variables
        """
        _list = await self._async_list()
        return self._filtered_watcher_vars(_list["watchers"], lambda var: not var["watched"])

    # --- connection methods --- #

    def connect(self):
        """Attempts to establish a WebSocket connection and prints a message indicating success or failure.

        """
        if self.is_connected():
            return "Already connected"

        async def _async_connect():
            try:
                # Close any open ctrl websocket open for the same mode (STREAM, LOG, MONITOR, WATCH)
                if self._pybela_ws_register[self._mode].get(self.ws_ctrl_add) is not None and self._pybela_ws_register[self._mode][self.ws_ctrl_add].state == 1:
                    _print_warning(
                        f"pybela doesn't support more than one active connection at a time for a given mode. Closing previous connection for {self._mode} at {self.ws_ctrl_add}.")
                    await self._pybela_ws_register[self._mode][self.ws_ctrl_add].close()
                    self._pybela_ws_register[self._mode][self.ws_ctrl_add].keepalive_task.cancel(
                    )

                # Control and monitor can't be used at the same time
                _is_control_mode_running = self._pybela_ws_register["CONTROL"].get(
                    self.ws_ctrl_add) is not None and self._pybela_ws_register["CONTROL"][self.ws_ctrl_add].state == 1
                _is_monitor_mode_running = self._pybela_ws_register["MONITOR"].get(
                    self.ws_ctrl_add) is not None and self._pybela_ws_register["MONITOR"][self.ws_ctrl_add].state == 1
                if (self._mode == "MONITOR" and _is_control_mode_running) or (self._mode == "CONTROL" and _is_monitor_mode_running):
                    _print_warning(
                        f"pybela doesn't support running control and monitor modes at the same time. You are currently running {'CONTROL' if self._mode=='MONITOR' else 'MONITOR'} at {self.ws_ctrl_add}. You can close it running controller.disconnect()")
                    _print_error("Connection failed")
                    return 0

                # Connect to the control websocket
                # try:
                self.ws_ctrl = await websockets.connect(self.ws_ctrl_add)
                # except asyncio.TimeoutError:
                #     _print_error(f"Timeout connecting to {self.ws_ctrl_add}")
                #     return 0
                self._pybela_ws_register[self._mode][self.ws_ctrl_add] = self.ws_ctrl

                # If connection is successful,
                #  (1) send connection reply to establish the connection
                # (2) connect to the data websocket
                # (3) start data processing and sending tasks
                # (4) start listener tasks
                # (5) refresh watcher vars in case new project has been loaded in Bela
                response = json.loads(await self.ws_ctrl.recv())
                if "event" in response and response["event"] == "connection":
                    self.project_name = response["projectName"]

                    # Send connection reply to establish the connection
                    await self._async_send_ctrl_msg({"event": "connection-reply"})

                    # Connect to the data websocket
                    self.ws_data = await websockets.connect(self.ws_data_add)

                    # start data sending and processing tasks
                    self._send_ctrl_msg_task = self.loop.create_task(
                        self._send_ctrl_msg_worker())
                    self._send_data_msg_task = self.loop.create_task(
                        self._send_data_msg_worker())
                    self._process_received_data_msg_task = self.loop.create_task(
                        self._process_data_msg_worker())

                    # start listener tasks
                    self._ctrl_listener_task = self.loop.create_task(self._async_start_listener(
                        self.ws_ctrl, self.ws_ctrl_add))
                    self._data_listener_task = self.loop.create_task(self._async_start_listener(
                        self.ws_data, self.ws_data_add))

                    # refresh watcher vars in case new project has been loaded in Bela
                    self._list = await self._async_list()
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

        return self.loop.run_until_complete(_async_connect())

    def is_connected(self):
        """Check if the websocket is connected
        Returns:
            bool: True if connected, False otherwise
        """

        return True if (self.ws_ctrl is not None and self.ws_ctrl.state == 1) and (self.ws_data is not None and self.ws_data.state == 1) else False

    async def _async_disconnect(self):
        """Disconnects the websockets. Closes the websockets and cancels the keepalive task."""
        # close websockets
        for ws in [self.ws_ctrl, self.ws_data]:
            if ws is not None and ws.state == 1:
                await ws.close()
                ws.keepalive_task.cancel()  # cancel keepalive task

    def disconnect(self):
        """Closes websockets. Sync wrapper for _async_disconnect.
        """
        self.loop.run_until_complete(self._async_disconnect())

    # -- ssh methods --

    def connect_ssh(self):
        """ Connects to Bela via ssh to transfer log files.
        """

        if self.sftp_client is not None:
            self.disconnect_ssh()

        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Workaround for no authentication:
        # https://github.com/paramiko/paramiko/issues/890#issuecomment-906893725
        try:
            self.ssh_client.connect(
                self.ip, port=22, username="root", password=None)
        except paramiko.SSHException as e:
            self.ssh_client.get_transport().auth_none("root")
        except Exception as e:
            _print_error(
                f"Error while connecting to Bela via ssh: {e}")
            return

        try:
            self.sftp_client = self.ssh_client.open_sftp()
            # _print_ok("SSH connection and SFTP client established successfully.")
        except Exception as e:
            _print_error(
                f"Error while opening SFTP client: {e}")
            self.disconnect_ssh()

    def disconnect_ssh(self):
        """ Disconnects from Bela via ssh.
        """
        if self.sftp_client:
            self.sftp_client.close()

    # -- cleanups -- #

    async def _async_cancel_tasks(self, tasks):
        """Cancels tasks
        """
        cancel_tasks = []
        for task in tasks:
            if task is not None and not task.done():
                task.cancel()
                cancel_tasks.append(task)
        await asyncio.gather(*cancel_tasks, return_exceptions=True)

    async def _async_cleanup(self):
        """Cleans up tasks
        """
        tasks = [self._ctrl_listener_task,
                 self._data_listener_task,
                 self._process_received_data_msg_task,
                 self._send_data_msg_task,
                 self._send_ctrl_msg_task
                 ]
        await self._async_cancel_tasks(tasks)
        await self._async_disconnect()

    def cleanup(self):
        """Cleans up tasks. Synchronous wrapper for _async_cleanup
        """
        self.loop.run_until_complete(self._async_cleanup())

    # --- message sending methods --- #

    async def _send_data_msg_worker(self):
        """ Send data message to websocket. Runs as long as websocket is open.
        """
        while self.ws_data is not None and self.ws_data.state == 1:
            msg = await self._to_send_data_msg_queue.get()
            await self.ws_data.send(msg)
            self._to_send_data_msg_queue.task_done()

    async def _send_ctrl_msg_worker(self):
        """ Send control message to websocket. Runs as long as websocket is open.
        """
        while self.ws_ctrl is not None and self.ws_ctrl.state == 1:
            msg = await self._to_send_ctrl_msg_queue.get()
            msg = json.dumps(msg)
            await self.ws_ctrl.send(msg)
            self._to_send_ctrl_msg_queue.task_done()

    async def _async_send_msg(self, ws_address, msg):
        """Send message to websocket

        Args:
            ws_address (str): Websocket address
            msg (str): Message to send
        """
        try:
            if ws_address == self.ws_data_add and self.ws_data is not None and self.ws_data.state == 1:
                self._to_send_data_msg_queue.put_nowait(msg)
            elif ws_address == self.ws_ctrl_add and self.ws_ctrl is not None and self.ws_ctrl.state == 1:
                # msg = json.dumps(msg)
                self._to_send_ctrl_msg_queue.put_nowait(msg)
        except Exception as e:
            _handle_connection_exception(ws_address, e, "sending message")
            return 0

    def _send_msg(self, ws_address, msg):
        """Send message to websocket. Sync wrapper for _async_send_msg. Can be used in synchronous functions.

        Args:
            ws_address (str): Websocket address
            msg (str): Message to send
        """
        return self.loop.create_task(self._async_send_msg(ws_address, msg))

    async def _async_send_ctrl_msg(self, msg):
        """Send control message. Async version of send_ctrl_msg.

        Args:
            msg (str): Message to send to the Bela watcher. Example: {"watcher": [{"cmd": "list"}]}
        """
        await self._async_send_msg(self.ws_ctrl_add, msg)

    def send_ctrl_msg(self, msg):
        """Send control message

        Args:
            msg (str): Message to send to the Bela watcher. Example: {"watcher": [{"cmd": "list"}]}
        """
        self._send_msg(self.ws_ctrl_add, msg)

    ##  -- list -- ##

    async def _async_list(self):
        """ Asks the watcher for the list of variables and their properties and returns it.

        Returns:
            dict: Dictionary with the list of variables and their properties
        """
        self.send_ctrl_msg({"watcher": [{"cmd": "list"}]})
        # Wait for the list response to be available
        list_res = await self._list_response_queue.get()
        self._list_response_queue.task_done()
        return list_res

    def list(self):
        """ Sync wrapper for _async_list
        """
        return self.loop.run_until_complete(self._async_list())

    # -- listener methods -- #

    async def _async_start_listener(self, ws, ws_address):
        """Start listener for websocket

        Args:
            ws (websockets.WebSocketClientProtocol): Websocket object
            ws_address (str): Websocket address
        """
        try:
            while ws is not None and ws.state == 1:
                msg = await ws.recv()
                if self._printall_responses:
                    print(msg)
                if ws_address == self.ws_data_add:
                    self._received_data_msg_queue.put_nowait(msg)
                elif ws_address == self.ws_ctrl_add:
                    _msg = json.loads(msg)
                    # response to list cmd
                    if "watcher" in _msg.keys() and "sampleRate" in _msg["watcher"].keys():
                        self._list_response_queue.put_nowait(
                            _msg["watcher"])
                else:
                    print(msg)

        except Exception as e:
            if ws.state == 1:  # otherwise websocket was closed intentionally
                _handle_connection_exception(
                    ws_address, e, "receiving message")

    # -- data processing methods -- #

    async def _process_data_msg_worker(self):
        """Process data message.

        Args:
            msg (str): Bytestring with data
        """

        while self.ws_data is not None and self.ws_data.state == 1:
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

                try:
                    ref_timestamp, *_buffer = struct.unpack('Q' + f"{_type}" * data_length
                                                            + 'I'*data_length, binary_data)
                except struct.error as e:
                    _print_error(
                        f"Error parsing buffer: {e}. Received buffer of length: {len(binary_data)}")
                    return None
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

    def wait(self, time_in_seconds=0):
        """Wait for a given amount of time. Can't be used in async functions. 
            Args:
                time_in_seconds (float, optional): Time to wait in seconds. If 0, it waits forever. Defaults to 0. 
        """
        if time_in_seconds < 0:
            raise ValueError("Time in seconds should be greater than 0.")
        elif time_in_seconds > 0:
            self.loop.run_until_complete(asyncio.sleep(time_in_seconds))
        else:
            async def wait_forever():
                await asyncio.Future()
            self.loop.run_until_complete(wait_forever())

    async def _async_get_latest_timestamp(self):
        """Get latest timestamp. Async version of get_latest_timestamp."""
        _list = await self._async_list()
        return _list["timestamp"]

    def get_latest_timestamp(self):
        """Get latest timestamp. Can't be used in async functions"""
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
        """Generate local filename. If the file already exists, add a number at the end of the filename.

        Args:
            local_path (str): Path to the file
        """
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

    def copy_file_from_bela(self, remote_path, local_path, verbose=True):
        """Copy a file from Bela onto the local machine.

        Args:
            remote_path (str): Path to the remote file to be copied.
            local_path (str): Path to the local file (where the file is copied to)
            verbose (bool, optional): Show info messages. Defaults to True.
        """
        self.connect_ssh()
        local_path = self.loop.run_until_complete(self._async_copy_file_from_bela(
            remote_path, local_path, verbose))
        self.disconnect_ssh()
        return local_path

    async def _async_copy_file_from_bela(self, remote_path, local_path, verbose=False):
        """ Copies a file from the remote path in Bela to the local path. This can be used any time to copy files from Bela to the host. 

        Args:
            remote_path (str): Path to the file in Bela.
            local_path (str): Path to the file in the local machine (where the file is copied to)
        """
        try:
            _local_path = None
            if os.path.exists(local_path):
                _local_path = self._generate_local_filename(local_path)
            else:
                _local_path = local_path
            transferred_event = asyncio.Event()
            def callback(transferred, to_transfer): return transferred_event.set(
            ) if transferred == to_transfer else None
            self.sftp_client.get(remote_path, _local_path, callback=callback)
            file_size = self.sftp_client.stat(remote_path).st_size
            await asyncio.wait_for(transferred_event.wait(), timeout=file_size*1e-4)
            if verbose:
                _print_ok(
                    f"\rTransferring {remote_path}-->{_local_path}... Done.")
            return local_path
        except asyncio.exceptions.TimeoutError:
            _print_error(
                f"Error while transferring file: TimeoutError.")
            return None
        except Exception as e:
            _print_error(f"Error while transferring file: {e}")
            return None

    # destructor

    def __del__(self):
        pass  # __del__ can't run asynchronous code, so cleanup() should be called manually


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
