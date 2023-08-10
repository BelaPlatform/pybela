import unittest
import asyncio
import os

from pyBela import Watcher, Streamer

# all tests should be run with Bela connected and the bela-watcher project running on the board


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

        streaming_vars = ["myvar", "myvar2"]

        streaming_buffer = streamer.stream_n_frames(
            variables=streaming_vars, n_frames=n_frames)

        types = [var["type"]
                 for var in streamer.watcher_vars if var["name"] in streaming_vars]
        min_buffer_size = min([streamer.get_buffer_size(_type)
                              for _type in types])
        n_buffers = -(-n_frames // min_buffer_size)

        self.assertTrue(all(len(streamer.streaming_buffers_data[
                        var]) > n_frames for var in streaming_vars), "The streamed flat buffers for every variable should have at least n_frames")

        self.assertTrue(all(len(streaming_buffer[
                        var]) == n_buffers for var in streaming_vars), "The streaming buffers queue should have at least n_frames/buffer_size buffers for every variable")

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

        await asyncio.sleep(0.5)  # wait for some data to be streamed

        streamer.stop_streaming(variables=streaming_vars)

        # check streaming mode is OFF after stop_streaming
        self.assertEqual(streamer._streaming_mode, "OFF",
                         "Streaming mode should be OFF after stop_streaming")

        loaded = {}
        for var in streaming_vars:
            # check buffers in streaming_buffers_queue have the right length
            self.assertTrue(all(len(buffer["data"]) % 256 == 0 for buffer in streamer.streaming_buffers_queue[var]),
                            "All buffers in streamer.streaming_buffers_queue should have a length multiple of 256")
            loaded[var] = streamer.load_data_from_file(
                f"{var}_{saving_filename}")
            # check that the loader buffers have the right length
            self.assertTrue(all(len(buffer["data"]) % 256 == 0 for buffer in loaded[var]),
                            "All loaded buffers should have a length multiple of 256")
            # check that the number of buffers saved is the same as the number of buffers in streamer.streaming_buffers_queue
            self.assertTrue(len(streamer.streaming_buffers_queue[var]) == len(loaded[var]),
                            "The number of buffers saved should be equal to the number of buffers in streamer.streaming_buffers_queue (considering the queue length is long enough)")

        # check continuity of frames
        types = [var["type"]
                 for var in streamer.watcher_vars if var["name"] in streaming_vars]
        for var, typ in zip(streaming_vars, types):
            for buffer in streamer.streaming_buffers_queue[var]:
                self.assertEqual(buffer["frame"], buffer["data"][0],
                                 "The frame and the first item of data buffer should be the same")
                self.assertEqual(buffer["frame"]+streamer.get_buffer_size(typ)-1, buffer["data"][-1],
                                 "The last data item should be equal to the frame plus the length of the buffer")  # this test will fail if the Bela program has been streaming for too long and there are truncating errors. If this test fails, try stopping and rerunning hte Bela program again

        for var in streaming_vars:
            if os.path.exists(f"{var}_{saving_filename}"):
                os.remove(f"{var}_{saving_filename}")

    def test_buffers(self):
        asyncio.run(self.async_test_buffers())


if __name__ == '__main__':
    unittest.main(verbosity=2)
