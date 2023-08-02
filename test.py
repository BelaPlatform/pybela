import unittest
import asyncio
import os

from pyBela import Watcher, Streamer

# all tests should be run with Bela connected and the watcher project running on the board



class test_Watcher(unittest.TestCase):

    print("test_Watcher...")

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

    print("test_Streamer...")

    async def async_stream_forever_modes(self):
        streamer = Streamer()
        streamer.start_streaming(variables=streamer.watcher_vars)
        self.assertEqual(streamer._streaming_mode, "FOREVER",
                         "Streaming mode should be FOREVER after start_streaming")
        await asyncio.sleep(0.5)
        streamer.stop_streaming(variables=streamer.watcher_vars)
        self.assertEqual(streamer._streaming_mode, "OFF",
                         "Streaming mode should be OFF after stop_streaming")

    def test_stream_forever_modes(self):
        asyncio.run(self.async_stream_forever_modes())

    def test_stream_n_frames(self):
        streamer = Streamer()
        n_frames = 100
        streaming_buffer = streamer.stream_n_frames(
            variables=streamer.watcher_vars, n_frames=n_frames)
        self.assertTrue(all(len(var_buffer) == n_frames for var_buffer in streaming_buffer.values(
        )), "All streamed variables should have the same length as the requested number of frames")

    async def async_streamed_variables(self):
        streamer = Streamer()
        # stream only the last variable
        streamer.start_streaming(variables=streamer.watcher_vars[-1])
        await asyncio.sleep(0.5)
        streamer.stop_streaming(variables=streamer.watcher_vars[-1])
        self.assertNotEqual(len(
            streamer.streaming_buffer[streamer.watcher_vars[-1]]), 0, "The streamed variable buffer should not be empty")

    def test_streamed_variables(self):
        asyncio.run(self.async_streamed_variables())

    async def async_save(self):
        streamer = Streamer()
        streamer.streaming_buffer_size = 1000
        saving_filename = "test_save.txt"

        for var in streamer.watcher_vars:
            if os.path.exists(f"{var}_{saving_filename}"):
                os.remove(f"{var}_{saving_filename}")

        streamer.start_streaming(variables=streamer.watcher_vars,
                                 saving_enabled=True, saving_filename=saving_filename)
        await asyncio.sleep(0.8) # wait for some data to be streamed
        streamer.stop_streaming(variables=streamer.watcher_vars)

        loaded = {}
        for var in streamer.watcher_vars:
            loaded[var] = streamer.load_data_from_file(f"{var}_{saving_filename}")


        self.assertTrue(all(len(streamer.streaming_buffer[var]) == len(loaded[var]) for var in streamer.watcher_vars),
                        "The loaded data should have the same length as the streamed data (considering the buffer size is large enough)")
        

        # for var in streamer.watcher_vars:
        #     if os.path.exists(f"{var}_{saving_filename}"):
        #         os.remove(f"{var}_{saving_filename}")
        
        # TODO test timeframes is the same in both variables

    def test_save(self):
        asyncio.run(self.async_save())


if __name__ == '__main__':
    # begin the unittest.main()
    unittest.main()
