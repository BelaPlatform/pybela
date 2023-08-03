import unittest
import asyncio
import os

from pyBela import Watcher, Streamer

# all tests should be run with Bela connected and the watcher project running on the board

class test_Watcher(unittest.TestCase):

    def test_list(self):
        watcher = Watcher()
        watcher.start()
        self.assertEqual(len(watcher.list()), len(watcher.watcher_vars),
                         "Length of list should be equal to number of watcher variables")

    def test_start_stop(self):
        watcher = Watcher()
        watcher.start()
        watcher.stop()
        self.assertEqual(watcher._ctrl_listener, None,
                         "Watcher ctrl listener should be None after stop")
        self.assertEqual(watcher._data_listener, None,
                         "Watcher data listener should be None after stop")


class test_Streamer(unittest.TestCase):

    def test_stream_n_frames(self):
        streamer = Streamer()
        n_frames = 2000
        streaming_buffer = streamer.stream_n_frames(
            variables=streamer.watcher_vars, n_frames=n_frames)
        
        n_buffers = -(-n_frames // streamer._streaming_buffer_size)

        self.assertTrue(all(len(var_buffer_queue) == n_buffers for var_buffer_queue in streaming_buffer.values(
        )), "All streamed variables should have the same length as the requested number of frames")

    async def async_test_buffers(self):
        streamer = Streamer()
        streamer.streaming_buffers_queue_length = 1000
        saving_filename = "test_save.txt"
        
        streaming_vars = ["myvar", "myvar2"]

        # delete any existing test files
        for var in streaming_vars:
            if os.path.exists(f"{var}_{saving_filename}"):
                os.remove(f"{var}_{saving_filename}")

        streamer.start_streaming(variables=streaming_vars,
                                 saving_enabled=True, saving_filename=saving_filename)
        
        # check streaming mode is FOREVER after start_streaming is called
        self.assertEqual(streamer._streaming_mode, "FOREVER",
                         "Streaming mode should be FOREVER after start_streaming")
        
        await asyncio.sleep(5) # wait for some data to be streamed
        
        streamer.stop_streaming(variables=streaming_vars)
        
        # check streaming mode is OFF after stop_streaming
        self.assertEqual(streamer._streaming_mode, "OFF",
                         "Streaming mode should be OFF after stop_streaming")

        loaded = {}
        for var in streaming_vars:
            # check buffers in streaming_buffers_queue have the right length
            self.assertTrue(all(len(buffer["data"]) == streamer._streaming_buffer_size for buffer in streamer.streaming_buffers_queue[var]), "All buffers in streamer.streaming_buffers_queue should have a length equal to the buffer size")
            loaded[var] = streamer.load_data_from_file(f"{var}_{saving_filename}")
            # check that the loader buffers have the right length
            self.assertTrue(all(len(buffer["data"]) == streamer._streaming_buffer_size for buffer in loaded[var]), "All loaded buffers should have a length equal to the buffer size")
            
        # check that the number of buffers saved is the same as the number of buffers in streamer.streaming_buffers_queue
        self.assertTrue(all(len(streamer.streaming_buffers_queue[var]) == len(loaded[var]) for var in streaming_vars),
                        "The number of buffers saved should be equal to the number of buffers in streamer.streaming_buffers_queue (considering the queue length is long enough)")
        # list of frames for each variable     
        frames = {var: [buffer["frame"] for buffer in streamer.streaming_buffers_queue[var]] for var in streamer.streaming_buffers_queue}
        # check the frames are the same for all variables 
        self.assertTrue(frames[streaming_vars[0]] == frames[streaming_vars[1]], "The frames in the buffers should be the same for all variables")
        
        # check continuity of frames
        for var in streaming_vars:
            for buffer in streamer.streaming_buffers_queue[var]:
                self.assertEqual(buffer["frame"], buffer["data"][0], "The frame and the first item of data buffer should be the same")
                self.assertEqual(buffer["frame"]+streamer._streaming_buffer_size-1, buffer["data"][-1], "The last data item should be equal to the frame plus the length of the buffer minus one.")
        
        delete saved files        
        for var in streaming_vars:
            if os.path.exists(f"{var}_{saving_filename}"):
                os.remove(f"{var}_{saving_filename}")
        
    def test_buffers(self):
        asyncio.run(self.async_test_buffers())


if __name__ == '__main__':
    unittest.main(verbosity=2)
