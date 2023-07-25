import asyncio
import array
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

    @property
    def streaming_buffer_size(self):
        return self._streaming_buffer_size

    @streaming_buffer_size.setter
    def streaming_buffer_size(self, value):
        self._streaming_buffer_size = value
        self._streaming_buffer = {var: deque(
            maxlen=self._streaming_buffer_size) for var in self._watcher_vars}  # resize streaming buffer

    @property
    def streaming_buffer(self):
        # convert dict of deque to dict of list
        return {key: list(value) for key, value in self._streaming_buffer.items()}

    def start(self):
        super(Streamer, self).start()
        self._streaming_buffer = {var: deque(
            maxlen=self._streaming_buffer_size) for var in self._watcher_vars}

    def start_streaming(self, variables=[]):  # stream forever until stopped
        # if no variables are specified, stream all watched variables
        if len(variables)==0:
            variables = self.watcher_vars
        variables = variables if isinstance(variables, list) else [variables]
            
        self.start()
        self._streaming_mode = "FOREVER"
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "watch", "watchers": variables}]})

    def stop_streaming(self, variables=[]):
        self.stop()
        self._streaming_mode = "OFF"
        if variables==[]:
            variables = self.watched_vars # stop streaming all watcher variables
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "unwatch", "watchers": variables}]})
        return self.streaming_buffer

    async def async_stream_n_frames(self, variables, n_frames):
        self.start()
        self._streaming_mode = "N_FRAMES"  # flag cleared in __rec_msg_callback
        # using setter to automatically resize buffer
        self.streaming_buffer_size = n_frames
     
        self.send_ctrl_msg({"cmd":"unwatch", "watchers":self.watched_vars}) # unwatch all variables
        self.send_ctrl_msg( # watch only the variables specified
            {"watcher": [{"cmd": "watch", "watchers": variables}]})

        # return when finished filling buffer
        await self._streaming_buffer_available.wait()
        self._streaming_buffer_available.clear()

        self.stop_streaming(variables) # turns off listener, unwatches variables

        return self.streaming_buffer

    # resizes the streaming buffer size to n_frames and returns it when full 
    def stream_n_frames(self, variables=[], n_frames=1000, delay=0): # blocks a cell because it waits for the result. in order not to block the cell, use the async version above

        # TODO implement delay once data comes timestamped
        
        # if no variables are specified, stream all watched variables
        if len(variables)==0:
            variables = self.watcher_vars
            
        variables = variables if isinstance(variables, list) else [variables]

        return asyncio.run(self.async_stream_n_frames(variables, n_frames))
    
    def is_streaming(self):
        return True if self.streaming_mode != "OFF" else False

    # TODO add saving to file
    
    
    def _parse_data_message(self, msg):
        global _type, _channel  #FIXME this is not very clean
        if self._streaming_mode != "OFF":
            if len(msg) == 3:
                _channel = int(str(msg)[2])
                _type = str(msg)[4]
            elif len(msg) > 3:
                _msg = array.array(_type, msg).tolist()
                self._streaming_buffer[self._watcher_vars[_channel]].extend(
                    _msg)  #FIXME this does not truncate once buffer size is reached 
                if self._streaming_mode == "N_FRAMES" and all(len(self._streaming_buffer[var]) == self._streaming_buffer_size for var in self._watcher_vars):
                    self._streaming_mode = "OFF"
                    self._streaming_buffer_available.set()
