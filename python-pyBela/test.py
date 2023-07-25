import unittest
import asyncio
from pyBela import Watcher, Streamer

class test_Watcher(unittest.TestCase):
    
    print("test_Watcher...")

    def test_list(self):
        # to be run with bela connected and running
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
    
    print("test_Streamer...")
    
    async def async_stream_forever_modes(self):
        streamer = Streamer()
        streamer.start_streaming(variables=streamer.watcher_vars)
        self.assertEqual(streamer._streaming_mode, "FOREVER","Streaming mode should be FOREVER after start_streaming")
        await asyncio.sleep(0.5)
        streamer.stop_streaming(variables=streamer.watcher_vars)
        self.assertEqual(streamer._streaming_mode, "OFF","Streaming mode should be OFF after stop_streaming")
        
    def test_stream_forever_modes(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.async_stream_forever_modes())
        
        
    def test_stream_n_frames(self):
        streamer = Streamer()
        streaming_buffer = streamer.stream_n_frames(variables=streamer.watcher_vars, n_frames=100)
        self.assertTrue(all(len(var_buffer) == streamer.streaming_buffer_size for var_buffer in streaming_buffer.values()))
        
    async def async_streamed_variables(self): 
        streamer = Streamer()
        streamer.start_streaming(variables=streamer.watcher_vars[-1]) # stream only the last variable
        await asyncio.sleep(0.5)
        streamer.stop_streaming(variables=streamer.watcher_vars[-1])
        self.assertNotEqual(len(streamer.streaming_buffer[streamer.watcher_vars[-1]]),0, "The streamed variable buffer should not be empty")
        
    def test_streamed_variables(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.async_streamed_variables())
        
    
if __name__ == '__main__':
    # begin the unittest.main()
    unittest.main()