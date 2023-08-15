import unittest
import asyncio
import os

from pyBela import Watcher, Streamer, Logger

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

        buffer_sizes = [
            streamer.get_data_length(var["type"], var["timestamp_mode"])
            for var in streamer.watcher_vars if var["name"] in streaming_vars]

        n_buffers = -(-n_frames // min(buffer_sizes))

        self.assertTrue(all(len(streamer.streaming_buffers_data[
                        var]) > n_frames for var in streaming_vars), "The streamed flat buffers for every variable should have at least n_frames")

        self.assertTrue(all(len(streaming_buffer[
                        var]) == n_buffers for var in streaming_vars), "The streaming buffers queue should have at least n_frames/buffer_size buffers for every variable")

    async def async_test_buffers(self):
        streamer = Streamer()
        streamer.streaming_buffers_queue_length = 1000
        saving_filename = "test_save.txt"

        streaming_vars = [
            "myvar",  # dense double
            "myvar2",  # dense uint
            "myvar3",  # sparse uint
            "myvar4"  # sparse double
        ]

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
        for var in [v for v in streamer.watcher_vars if v["name"] in streaming_vars]:

            # check buffers in streaming_buffers_queue have the right length
            self.assertTrue(all(len(buffer["data"]) == var["data_length"] for buffer in streamer.streaming_buffers_queue[var["name"]]),
                            f"The data buffers in streamer.streaming_buffers_queue should have a length of {var['data_length']} for a variable of type {var['type']} ")
            loaded[var["name"]] = streamer.load_data_from_file(
                f"{var['name']}_{saving_filename}")
            # check that the loader buffers have the right length
            self.assertTrue(all(len(buffer["data"]) == var["data_length"] for buffer in loaded[var['name']]),
                            "The loaded data buffers should have a length of {var['data_length']} for a variable of type {var['type']} ")
            # check that the number of buffers saved is the same as the number of buffers in streamer.streaming_buffers_queue
            self.assertTrue(len(streamer.streaming_buffers_queue[var['name']]) == len(loaded[var['name']]),
                            "The number of buffers saved should be equal to the number of buffers in streamer.streaming_buffers_queue (considering the queue length is long enough)")

        # check continuity of frames (only works for dense variables)
        dense_vars = ["myvar", "myvar2"]
        types = [var["type"]
                 for var in streamer.watcher_vars if var["name"] in dense_vars]
        for var in [v for v in streamer.watcher_vars if v["name"] in dense_vars]:
            for buffer in streamer.streaming_buffers_queue[var["name"]]:
                self.assertEqual(buffer["ref_timestamp"], buffer["data"][0],
                                 "The ref_timestamp and the first item of data buffer should be the same")
                self.assertEqual(buffer["ref_timestamp"]+var["data_length"]-1, buffer["data"][-1],
                                 "The last data item should be equal to the ref_timestamp plus the length of the buffer")  # this test will fail if the Bela program has been streaming for too long and there are truncating errors. If this test fails, try stopping and rerunning hte Bela program again

        for var in streaming_vars:
            if os.path.exists(f"{var}_{saving_filename}"):
                os.remove(f"{var}_{saving_filename}")

    def test_buffers(self):
        asyncio.run(self.async_test_buffers())


class test_Logger(unittest.TestCase):
    async def async_test_logged_files(self):
        logger = Logger()

        local_paths = logger.start_logging(variables=["myvar"], transfer=True)

        await asyncio.sleep(2)
        logger.stop_logging()
        self.assertTrue(os.path.exists(
            local_paths["myvar"]), "The logged file should exist after logging")

        # logger.copy_file_from_bela( "/root/Bela/projects/watcher/myvar.bin", "test_myvar.bin")

        for var in local_paths:
            if os.path.exists(local_paths[var]):
                os.remove(local_paths[var])

        # test log

    def test_logged_files(self):
        asyncio.run(self.async_test_logged_files())


if __name__ == '__main__':
    # unittest.main(verbosity=2)
    suite = unittest.TestSuite()
    suite.addTest(test_Logger('test_logged_files'))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
