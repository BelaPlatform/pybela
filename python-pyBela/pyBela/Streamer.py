import asyncio
import array
import pickle
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

    def start_streaming(self, variables=[], saving_enabled=False, saving_filename=None):  # stream forever until stopped
        self._saving_enabled = True if saving_enabled else False
        self._saving_filename = "streamed_data.pkl" if saving_filename is None and saving_enabled else saving_filename
        # if no variables are specified, stream all watched variables
        if len(variables)==0:
            variables = self.watcher_vars
        variables = variables if isinstance(variables, list) else [variables]
            
        self.start()
        self._streaming_mode = "FOREVER"
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "watch", "watchers": variables}]})

    async def async_stop_streaming(self, variables=[]):
        self.stop()
        self._streaming_mode = "OFF"
        
        if self._saving_enabled:
            self._saving_enabled = False
            self._saving_filename = None
            await asyncio.gather(*self._active_saving_tasks, return_exceptions=True) # await last self._saving_task
            #self._saving_task.cancel()  
            self._active_saving_tasks.clear()
        
        if variables==[]:
            variables = self.watched_vars # stop streaming all watcher variables
        self.send_ctrl_msg(
            {"watcher": [{"cmd": "unwatch", "watchers": variables}]})
        
        return self.streaming_buffer

    def stop_streaming(self, variables=[]):
        return asyncio.run(self.async_stop_streaming(variables))


    async def async_stream_n_frames(self, variables, n_frames, saving_enabled=False, saving_filename=None):
        self._saving_enabled = True if saving_enabled else False
        self._saving_filename = "streamed_data.pkl" if saving_filename is None and saving_enabled else saving_filename

        # if no variables are specified, stream all watched variables
        if len(variables)==0:
            variables = self.watcher_vars
        variables = variables if isinstance(variables, list) else [variables]
        
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
    def stream_n_frames(self, variables=[], n_frames=1000, delay=0, saving_enabled=False, filename=None): # blocks a cell because it waits for the result. in order not to block the cell, use the async version above
        # TODO implement delay once data comes timestamped
        return asyncio.run(self.async_stream_n_frames(variables, n_frames, saving_enabled, filename))
    
    def is_streaming(self):
        return True if self.streaming_mode != "OFF" else False

        
    def _parse_data_message(self, msg):
        global _type, _channel 
        if self._streaming_mode != "OFF":
            if len(msg) == 3:
                _channel = int(str(msg)[2])
                _type = str(msg)[4]
            elif len(msg) > 3:
                _msg = array.array(_type, msg).tolist()
                self._streaming_buffer[self._watcher_vars[_channel]].extend(
                    _msg)  #FIXME this does not truncate once buffer size is reached 
                _save_obj = dict({self._watcher_vars[_channel]: _msg})
                
                if self._saving_enabled:
                    # Save the data asynchronously
                    saving_task = asyncio.create_task(self._save_data_to_file(self._saving_filename, _save_obj))
                    saving_task.add_done_callback(self._remove_finished_task)
                    self._active_saving_tasks.append(saving_task) # FIXME racing conditions?

                if self._streaming_mode == "N_FRAMES" and all(len(self._streaming_buffer[var]) == self._streaming_buffer_size for var in self._watcher_vars):
                    self._streaming_mode = "OFF"
                    self._streaming_buffer_available.set()
                    
    async def _save_data_to_file(self, filename, data_obj):
        # TODO warning if file already exists
        try:
            while self._saving_enabled:
                data_to_save = dict(data_obj)

                with open(filename, "ab+") as f:  # Open the file in binary append mode
                    # Serialize the data and append it to the file using the highest protocol
                    pickle.dump(data_to_save, f, protocol=pickle.HIGHEST_PROTOCOL)

                # Wait for a short interval before writing the next update
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error while saving data to file: {e}")
            
    
    # TODO test -- start saving but streaming is running already 
    def save_data_as_it_comes(self, filename):
        self._saving_enabled = True
        self._saving_filename = filename

    def stop_saving_data(self):
        self._saving_enabled = False
        self._saving_filename = None
        
    def load_data_from_file(self, filename):
        try:
            data = {}
            with open(filename, "rb") as f:  # Open the file in binary read mode
                while True:
                    try:
                        # Load the next object from the file
                        data_obj = pickle.load(f)

                        # Update the data dictionary with the contents of the loaded object
                        data.update(data_obj)
                    except EOFError:
                        # Reached the end of the file
                        break

                return data
        except Exception as e:
            print(f"Error while loading data from file: {e}")
            return None

    def _remove_finished_task(self, task):
        self._active_saving_tasks.remove(task)

