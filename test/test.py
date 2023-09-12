import unittest
import asyncio
import os
from pyBela import Watcher, Streamer, Logger, Monitor

# all tests should be run with Bela connected and the bela-watcher project running on the board


class test_Watcher(unittest.TestCase):

    def test_list(self):
        watcher = Watcher()
        watcher.connect()
        self.assertEqual(len(watcher.list()), len(watcher.watcher_vars),
                         "Length of list should be equal to number of watcher variables")

    def test_start_stop(self):
        watcher = Watcher()
        watcher.connect()
        watcher.stop()
        self.assertEqual(watcher._ctrl_listener, None,
                         "Watcher ctrl listener should be None after stop")
        self.assertEqual(watcher._data_listener, None,
                         "Watcher data listener should be None after stop")


class test_Streamer(unittest.TestCase):

    def test_stream_n_frames(self):
        streamer = Streamer()
        streamer.connect()
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

    def test_buffers(self):
        async def async_test_buffers():
            streamer = Streamer()
            streamer.connect()
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

            # check streaming mode is STREAM_FOREVER after start_streaming is called
            self.assertEqual(streamer._streaming_mode, "STREAM_FOREVER",
                             "Streaming mode should be STREAM_FOREVER after start_streaming")

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

            for var in [v for v in streamer.watcher_vars if v["name"] in dense_vars]:
                for _buffer in streamer.streaming_buffers_queue[var["name"]]:
                    self.assertEqual(_buffer["ref_timestamp"], _buffer["data"][0],
                                     "The ref_timestamp and the first item of data buffer should be the same")
                    self.assertEqual(_buffer["ref_timestamp"]+var["data_length"]-1, _buffer["data"][-1],
                                     "The last data item should be equal to the ref_timestamp plus the length of the buffer")  # this test will fail if the Bela program has been streaming for too long and there are truncating errors. If this test fails, try stopping and rerunning hte Bela program again

            for var in streaming_vars:
                if os.path.exists(f"{var}_{saving_filename}"):
                    os.remove(f"{var}_{saving_filename}")

        asyncio.run(async_test_buffers())


class test_Logger(unittest.TestCase):

    def test_logged_files(self):
        async def async_test_logged_files():
            logger = Logger()
            logger.connect()
            logging_vars = [
                "myvar",  # dense double
                "myvar2",  # dense uint
                "myvar3",  # sparse uint
                "myvar4"  # sparse double
            ]

            local_paths = logger.start_logging(
                variables=logging_vars, transfer=True)
            await asyncio.sleep(0.5)
            logger.stop_logging()

            data = {}
            for var in logging_vars:

                self.assertTrue(os.path.exists(
                    local_paths[var]), "The logged file should exist after logging")

                data[var] = logger.read_binary_file(
                    file_path=local_paths[var], timestamp_mode=logger.get_prop_of_var(var, "timestamp_mode"))

                # test data
                timestamp_mode = logger.get_prop_of_var(var, "timestamp_mode")
                for _buffer in data[var]["buffers"]:
                    self.assertEqual(_buffer["ref_timestamp"], _buffer["data"][0],
                                     "The ref_timestamp and the first item of data buffer should be the same")
                    self.assertEqual(logger.get_prop_of_var(var, "data_length"), len(_buffer["data"]),
                                     "The length of the buffer should be equal to the data_length property of the variable")
                    if _buffer["data"][-1] == 0:  # buffer has padding at the end
                        continue
                    if timestamp_mode == "dense":
                        self.assertEqual(_buffer["ref_timestamp"]+logger.get_prop_of_var(var, "data_length")-1, _buffer["data"][-1],
                                         "The last data item should be equal to the ref_timestamp plus the length of the buffer")
                    elif timestamp_mode == "sparse":
                        inferred_timestamps = [_ + _buffer["ref_timestamp"]
                                               for _ in _buffer["rel_timestamps"]]
                        self.assertEqual(
                            inferred_timestamps, _buffer["data"], "The timestamps should be equal to the ref_timestamp plus the relative timestamps (sparse logging)")

            for var in local_paths:
                if os.path.exists(local_paths[var]):
                    os.remove(local_paths[var])
        asyncio.run(async_test_logged_files())


class test_Monitor(unittest.TestCase):

    def test_monitor(self):
        async def async_test_monitor():
            monitor = Monitor()
            monitor.connect()
            monitor.start_monitoring(
                variables=["myvar", "myvar2"], periods=[1000, 1000])
            await asyncio.sleep(0.5)
            monitor.stop_monitoring()

        asyncio.run(async_test_monitor())

    def test_peek(self):
        async def async_test_peek():
            monitor = Monitor()
            monitor.connect()
            monitor.peek(
                variables=["myvar", "myvar2"])

        asyncio.run(async_test_peek())


if __name__ == '__main__':
    # unittest.main(verbosity=2)
    suite = unittest.TestSuite()
    # suite.addTest(test_Logger('test_logged_files'))
    suite.addTest(test_Monitor('test_peek'))
    suite.addTest(test_Monitor('test_monitor'))
    # suite.addTest(test_Streamer('test_buffers'))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
