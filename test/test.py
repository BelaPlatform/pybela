import unittest
import asyncio
import os
import numpy as np
from pyBela import Watcher, Streamer, Logger, Monitor

# all tests should be run with Bela connected and the bela-test project (in test/bela-test) running on the board


class test_Watcher(unittest.TestCase):

    def test_list(self):
        watcher = Watcher()
        watcher.connect()
        self.assertEqual(len(watcher.list()["watchers"]), len(watcher.watcher_vars),
                         "Length of list should be equal to number of watcher variables")

    def test_start_stop(self):
        watcher = Watcher()
        watcher.connect()
        watcher.stop_ws()
        self.assertEqual(watcher._ctrl_listener, None,
                         "Watcher ctrl listener should be None after stop")
        self.assertEqual(watcher._data_listener, None,
                         "Watcher data listener should be None after stop")


class test_Streamer(unittest.TestCase):

    def test_stream_n_values(self):
        streamer = Streamer()
        streamer.connect()
        n_values = 500

        streaming_vars = ["myvar", "myvar2"]

        streaming_buffer = streamer.stream_n_values(
            variables=streaming_vars, n_values=n_values)

        buffer_sizes = [
            streamer.get_data_length(var["type"], var["timestamp_mode"])
            for var in streamer.watcher_vars if var["name"] in streaming_vars]

        n_buffers = -(-n_values // min(buffer_sizes))

        self.assertTrue(all(len(streamer.streaming_buffers_data[
                        var]) > n_values for var in streaming_vars), "The streamed flat buffers for every variable should have at least n_values")

        self.assertTrue(all(len(streaming_buffer[
                        var]) == n_buffers for var in streaming_vars), "The streaming buffers queue should have at least n_values/buffer_size buffers for every variable")

    def test_buffers(self):

        async def async_test_buffers():
            streamer = Streamer()
            streamer.connect()
            streamer.streaming_buffers_queue_length = 1000
            saving_filename = "test_streamer_save.txt"

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

            for var in [v for v in streamer.watcher_vars if v["name"] in streaming_vars]:

                # check buffers in streaming_buffers_queue have the right length
                self.assertTrue(all(len(_buffer["data"]) == var["data_length"] for _buffer in streamer.streaming_buffers_queue[var["name"]]),
                                f"The data buffers in streamer.streaming_buffers_queue should have a length of {var['data_length']} for a variable of type {var['type']} ")
                loaded = streamer.load_data_from_file(
                    f"{var['name']}_{saving_filename}")
                # check that the loader buffers have the right length
                self.assertTrue(all(len(_buffer["data"]) == var["data_length"] for _buffer in loaded),
                                "The loaded data buffers should have a length of {var['data_length']} for a variable of type {var['type']} ")
                # check that the number of buffers saved is the same as the number of buffers in streamer.streaming_buffers_queue
                self.assertTrue(len(streamer.streaming_buffers_queue[var['name']]) == len(loaded),
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

    def _test_logged_data(self, logger, logging_vars, local_paths):
        # common routine to test the data in the logged files
        data = {}
        for var in logging_vars:

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
                                     f"{var} {local_paths[var]} The last data item should be equal to the ref_timestamp plus the length of the buffer")
                elif timestamp_mode == "sparse":
                    inferred_timestamps = [_ + _buffer["ref_timestamp"]
                                           for _ in _buffer["rel_timestamps"]]
                    self.assertEqual(
                        inferred_timestamps, _buffer["data"], "The timestamps should be equal to the ref_timestamp plus the relative timestamps (sparse logging)")

    def test_logged_files_with_transfer(self):
        async def async_test_logged_files_with_transfer():

            logging_dir = "./test"

            logger = Logger()
            logger.connect()

            logging_vars = [
                "myvar",  # dense double
                "myvar2",  # dense uint
                "myvar3",  # sparse uint
                "myvar4"  # sparse double
            ]

            file_paths = logger.start_logging(
                variables=logging_vars, transfer=True, logging_dir=logging_dir)
            await asyncio.sleep(0.5)
            logger.stop_logging()

            self._test_logged_data(logger, logging_vars,
                                   file_paths["local_paths"])

            # clean local log files
            for var in file_paths["local_paths"]:
                if os.path.exists(file_paths["local_paths"][var]):
                    os.remove(file_paths["local_paths"][var])

            # clean all remote log files in project
            logger.delete_all_bin_files_in_project()

        asyncio.run(async_test_logged_files_with_transfer())

    def test_logged_files_wo_transfer(self):
        async def async_test_logged_files_wo_transfer():
            logger = Logger()
            logger.connect()

            logging_vars = [
                "myvar",  # dense double
                "myvar2",  # dense uint
                "myvar3",  # sparse uint
                "myvar4"  # sparse double
            ]
            logging_dir = "./test"
            file_paths = logger.start_logging(
                variables=logging_vars, transfer=False, logging_dir=logging_dir)
            await asyncio.sleep(0.5)
            logger.stop_logging()
            local_paths = {}
            for var in file_paths["remote_paths"]:
                filename = os.path.basename(file_paths["remote_paths"][var])
                local_paths[var] = logger._generate_local_filename(
                    os.path.join(logging_dir, filename))
                logger.copy_file_from_bela(remote_path=file_paths["remote_paths"][var],
                                           local_path=local_paths[var])

            self._test_logged_data(logger, logging_vars, local_paths)

            # clean local log files
            for var in local_paths:
                if os.path.exists(local_paths[var]):
                    os.remove(local_paths[var])

            # clean all remote log files in project
            for var in file_paths["remote_paths"]:
                logger.delete_file_from_bela(file_paths["remote_paths"][var])

        asyncio.run(async_test_logged_files_wo_transfer())

    def test_scheduling_logging(self):
        async def async_test_scheduling_logging():
            logger = Logger()
            logger.connect()
            logging_dir = "./"

            logging_vars = [
                "myvar",  # dense double
                # "myvar2",  # dense uint
                # "myvar3",  # sparse uint
                # "myvar4"  # sparse double
            ]

            latest_timestamp = logger.get_latest_timestamp()
            sample_rate = logger.sample_rate
            timestamps = [latest_timestamp +
                          2*sample_rate, latest_timestamp+2*sample_rate + 5*sample_rate]

            file_paths = logger.schedule_logging(variables=logging_vars,
                                                 timestamps=timestamps,
                                                 transfer=True,
                                                 logging_dir=logging_dir)

            self._test_logged_data(logger, logging_vars,
                                   file_paths["local_paths"])

            # FIXME this test doesn't fail but scheduling doesn't work -- it doesn't stop at the second timestamp and it runs forever
            # clean local log files
            for var in file_paths["local_paths"]:
                if os.path.exists(file_paths["local_paths"][var]):
                    os.remove(file_paths["local_paths"][var])

            # clean all remote log files in project
            for var in file_paths["remote_paths"]:
                logger.delete_file_from_bela(file_paths["remote_paths"][var])
            await asyncio.sleep(2)
            logger.stop_logging()

        asyncio.run(async_test_scheduling_logging())


class test_Monitor(unittest.TestCase):
    def test_peek(self):
        async def async_test_peek():
            monitor = Monitor()
            monitor.connect()
            peeked_values = monitor.peek()  # peeks at all variables by default
            for var in peeked_values:
                self.assertEqual(peeked_values[var]["timestamp"], peeked_values[var]["value"],
                                 "The timestamp of the peeked variable should be equal to the value")
        asyncio.run(async_test_peek())

    def test_period_monitor(self):
        async def async_test_period_monitor():
            period = 1000

            monitor_vars = ["myvar", "myvar2"]  # assigned at every frame n

            monitor = Monitor()
            monitor.connect()
            monitor.start_monitoring(
                variables=monitor_vars,
                periods=[period]*len(monitor_vars))
            await asyncio.sleep(0.5)
            monitored_values = monitor.stop_monitoring()

            for var in monitor_vars:
                self.assertTrue(np.all(np.diff(monitored_values[var]["timestamps"]) == period),
                                "The timestamps of the monitored variables should be spaced by the period")
                if var in ["myvar", "myvar2"]:  # assigned at each frame n
                    self.assertTrue(np.all(np.diff(monitored_values[var]["values"]) == period),
                                    "The values of the monitored variables should be spaced by the period")

        asyncio.run(async_test_period_monitor())

    def test_monitor_n_values(self):

        async def async_test_monitor_n_values():
            period = 1000
            n_values = 25

            monitor_vars = ["myvar", "myvar2"]  # assigned at every frame n

            monitor = Monitor()
            monitor.connect()
            monitored_buffer = monitor.monitor_n_values(
                variables=monitor_vars, periods=[period]*len(monitor_vars), n_values=n_values)

            for var in monitor_vars:
                self.assertTrue(np.all(np.diff(monitor.values[var]["timestamps"]) == period),
                                "The timestamps of the monitored variables should be spaced by the period")
                self.assertTrue(np.all(np.diff(monitor.values[var]["values"]) == period),
                                "The values of the monitored variables should be spaced by the period")
                self.assertTrue(all(len(monitor.streaming_buffers_data[
                    var]) >= n_values for var in monitor_vars), "The streamed flat buffers for every variable should have at least n_values")
                self.assertTrue(all(len(monitored_buffer[
                    var]) == n_values for var in monitor_vars), "The streaming buffers queue should have at least n_values/buffer_size buffers for every variable")

        asyncio.run(async_test_monitor_n_values())

    def test_save_monitor(self):
        async def async_test_save_monitor():
            period = 1000
            saving_filename = "test_monitor_save.txt"

            monitor_vars = ["myvar",
                            "myvar2",
                            "myvar3",
                            "myvar4"
                            ]

            # delete any existing test files
            for var in monitor_vars:
                if os.path.exists(f"{var}_{saving_filename}"):
                    os.remove(f"{var}_{saving_filename}")

            monitor = Monitor()
            monitor.connect()
            monitor.start_monitoring(
                variables=monitor_vars,
                periods=[period]*len(monitor_vars),
                saving_enabled=True,
                saving_filename=saving_filename)
            await asyncio.sleep(0.5)
            monitor.stop_monitoring()

            for var in monitor_vars:
                monitored_buffers = monitor.streaming_buffers_queue[var]
                loaded_buffers = monitor.load_data_from_file(
                    f"{var}_{saving_filename}")
                for loaded_buffer, monitored_buffer in zip(loaded_buffers, monitored_buffers):

                    self.assertEqual(loaded_buffer["ref_timestamp"], monitored_buffer["ref_timestamp"],
                                     "The ref_timestamp of the loaded buffer should be equal to the ref_timestamp of the monitored buffer")
                    self.assertEqual(loaded_buffer["data"], monitored_buffer["data"],
                                     "The data of the loaded buffer should be equal to the data of the monitored buffer")
            for var in monitor_vars:
                if os.path.exists(f"{var}_{saving_filename}"):
                    os.remove(f"{var}_{saving_filename}")

        asyncio.run(async_test_save_monitor())


if __name__ == '__main__':
    # # run all tests
    unittest.main(verbosity=2)

    # # select which tests to run
    # suite = unittest.TestSuite()

    # suite.addTest(test_Watcher('test_list'))
    # suite.addTest(test_Watcher('test_start_stop'))

    # suite.addTest(test_Streamer('test_stream_n_values'))
    # suite.addTest(test_Streamer('test_buffers'))

    # suite.addTest(test_Logger('test_logged_files_with_transfer'))
    # suite.addTest(test_Logger('test_logged_files_wo_transfer'))
    # suite.addTest(test_Logger('test_scheduling_logging'))

    # suite.addTest(test_Monitor('test_peek'))
    # suite.addTest(test_Monitor('test_period_monitor'))
    # suite.addTest(test_Monitor('test_monitor_n_values'))
    # suite.addTest(test_Monitor('test_save_monitor'))

    # runner = unittest.TextTestRunner(verbosity=2)
    # runner.run(suite)
