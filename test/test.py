import unittest
import asyncio
import os
import numpy as np
from pybela import Watcher, Streamer, Logger, Monitor, Controller

os.environ["PYTHONASYNCIODEBUG"] = "1"

# all tests should be run with Bela connected and the bela-test project (in test/bela-test) running on the board

class test_Watcher(unittest.TestCase):

    def setUp(self):
        self.watcher = Watcher()
        self.watcher.connect()

    def tearDown(self):
        self.watcher.__del__()

    def test_list(self):
        self.assertEqual(len(self.watcher.list()["watchers"]), len(self.watcher.watcher_vars),
                         "Length of list should be equal to number of watcher variables")

    def test_start_stop(self):
        self.watcher.stop()
        self.assertTrue(self.watcher.ws_ctrl.close,
                        "Watcher ctrl websocket should be closed after stop")
        self.assertTrue(self.watcher.ws_data.close,
                        "Watcher data websocket should be closed after stop")


class test_Streamer(unittest.TestCase):

    def setUp(self):
        self.streamer = Streamer()
        self.streamer.connect()
        self.streaming_vars = [
            "myvar",  # dense double
            "myvar2",  # dense uint
            "myvar3",  # sparse uint
            "myvar4"  # sparse double
        ]
        self.saving_dir = "./test"

        self.saving_filename = "test_streamer_save.txt"

    def tearDown(self):
        self.streamer.__del__()

    def test_stream_n_values(self):
        n_values = 40

        streaming_buffer = self.streamer.stream_n_values(
            variables=self.streaming_vars[:2], n_values=n_values)

        # calc number of buffers needed to get n_values
        buffer_sizes = [
            self.streamer.get_data_length(var["type"], var["timestamp_mode"])
            for var in self.streamer.watcher_vars if var["name"] in self.streaming_vars[:2]]
        n_buffers = -(-n_values // min(buffer_sizes))

        # test data
        self.assertTrue(all(len(self.streamer.streaming_buffers_data[
                        var]) >= n_values for var in self.streaming_vars[:2]), "The streamed flat buffers for every variable should have at least n_values")
        self.assertTrue(all(len(streaming_buffer[
                        var]) == n_buffers for var in self.streaming_vars[:2]), "The streaming buffers queue should have at least n_values/buffer_size buffers for every variable")

    def __test_buffers(self, mode):
        # test data
        for var in [v for v in self.streamer.watcher_vars if v["name"] in self.streaming_vars]:

            # check buffers in streaming_buffers_queue have the right length
            self.assertTrue(all(len(_buffer["data"]) == var["data_length"] for _buffer in self.streamer.streaming_buffers_queue[var["name"]]),
                            f"The data buffers in self.streamer.streaming_buffers_queue should have a length of {var['data_length']} for a variable of type {var['type']} ")
            loaded = self.streamer.load_data_from_file(
                os.path.join(self.saving_dir, f"{var['name']}_{self.saving_filename}"))
            # check that the loader buffers have the right length
            self.assertTrue(all(len(_buffer["data"]) == var["data_length"] for _buffer in loaded),
                            "The loaded data buffers should have a length of {var['data_length']} for a variable of type {var['type']} ")
            # check that the number of buffers saved is the same as the number of buffers in self.streamer.streaming_buffers_queue
            self.assertTrue(len(self.streamer.streaming_buffers_queue[var['name']]) == len(loaded),
                            "The number of buffers saved should be equal to the number of buffers in self.streamer.streaming_buffers_queue (considering the queue length is long enough)")

        # check continuity of frames (only works for dense variables)
        if mode != "schedule":
            for var in [v for v in self.streamer.watcher_vars if v["name"] in self.streaming_vars[:2]]:
                for _buffer in self.streamer.streaming_buffers_queue[var["name"]]:
                    self.assertEqual(_buffer["ref_timestamp"], _buffer["data"][0],
                                     "The ref_timestamp and the first item of data buffer should be the same")
                    self.assertEqual(_buffer["ref_timestamp"]+var["data_length"]-1, _buffer["data"][-1],
                                     "The last data item should be equal to the ref_timestamp plus the length of the buffer")  # this test will fail if the Bela program has been streaming for too long and there are truncating errors. If this test fails, try stopping and rerunning hte Bela program again

        for var in self.streaming_vars:
            remove_file(os.path.join(self.saving_dir,
                        f"{var}_{self.saving_filename}"))

    def test_start_stop_streaming(self):
        self.streamer.streaming_buffers_queue_length = 1000

        # delete any existing test files
        for var in self.streaming_vars:
            remove_file(os.path.join(self.saving_dir,
                                     f"{var}_{self.saving_filename}"))

        # stream with saving
        self.streamer.start_streaming(variables=self.streaming_vars,
                                      saving_enabled=True, saving_filename=self.saving_filename, saving_dir=self.saving_dir)
        # check streaming mode is FOREVER after start_streaming is called
        self.assertEqual(self.streamer._streaming_mode, "FOREVER",
                         "Streaming mode should be FOREVER after start_streaming")
        asyncio.run(asyncio.sleep(0.5))  # wait for some data to be streamed
        self.streamer.stop_streaming(variables=self.streaming_vars)
        # check streaming mode is OFF after stop_streaming

        self.assertEqual(self.streamer._streaming_mode, "OFF",
                         "Streaming mode should be OFF after stop_streaming")
        self.__test_buffers(mode="start_stop")

    def test_scheduling_streaming(self):
        self.streamer.streaming_buffers_queue_length = 1000
        latest_timestamp = self.streamer.get_latest_timestamp()
        sample_rate = self.streamer.sample_rate
        timestamps = [latest_timestamp +
                        sample_rate] * len(self.streaming_vars)  # start streaming after ~1s
        durations = [sample_rate] * \
            len(self.streaming_vars)  # stream for 1s

        self.streamer.schedule_streaming(variables=self.streaming_vars,
                                            timestamps=timestamps,
                                            durations=durations,
                                            saving_enabled=True,
                                            saving_dir=self.saving_dir,
                                            saving_filename=self.saving_filename)

        self.__test_buffers(mode="schedule")

    def test_on_buffer_callback(self):
        variables = ["myvar", "myvar5"]  # dense double

        # test only on vars of the same type

        timestamps = {var: [] for var in variables}
        buffers = {var: [] for var in variables}

        def callback(buffer):
            timestamps[buffer["name"]].append(
                buffer["buffer"]["ref_timestamp"])
            buffers[buffer["name"]].append(buffer["buffer"]["data"])

        self.streamer.start_streaming(
            variables, saving_enabled=False, on_buffer_callback=callback)

        asyncio.run(asyncio.sleep(0.1))

        self.streamer.stop_streaming(variables)

        for var in variables:
            for i in range(1, len(timestamps[var])):
                self.assertEqual(timestamps[var][i] - timestamps[var][i-1], 512,
                                 "The timestamps should be continuous. The callback is missing some buffer")

    def test_on_block_callback(self):
        variables = ["myvar", "myvar5"]  # dense double

        timestamps = {var: [] for var in variables}
        buffers = {var: [] for var in variables}

        def callback(block):
            for buffer in block:
                var = buffer["name"]
                timestamps[var].append(buffer["buffer"]["ref_timestamp"])
                buffers[var].append(buffer["buffer"]["data"])

        self.streamer.start_streaming(
            variables, saving_enabled=False, on_block_callback=callback)

        asyncio.run(asyncio.sleep(0.5))

        self.streamer.stop_streaming(variables)
        
        self.assertGreater(len(timestamps["myvar"]), 0, "The on_block_callback should have been called at least once")
        
        for var in variables:
            for i in range(1, len(timestamps[var])):
                self.assertEqual(timestamps[var][i] - timestamps[var][i-1], 512,
                                 "The timestamps should be continuous. The callback is missing some buffer")


class test_Logger(unittest.TestCase):

    def setUp(self):
        self.logger = Logger()
        self.logger.connect()

        self.logging_vars = [
            "myvar",  # dense double
            "myvar2",  # dense uint
            "myvar3",  # sparse uint
            "myvar4"  # sparse double
        ]
        self.logging_dir = "./test"

    def tearDown(self):
        self.logger.__del__()

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
        # log with transfer
        file_paths = self.logger.start_logging(
            variables=self.logging_vars, transfer=True, logging_dir=self.logging_dir)
        asyncio.run(asyncio.sleep(0.5))
        self.logger.stop_logging()

        # test logged data
        self._test_logged_data(self.logger, self.logging_vars,
                                file_paths["local_paths"])

        # clean local log files
        for var in file_paths["local_paths"]:
            remove_file(file_paths["local_paths"][var])
        # clean all remote log files in project
        self.logger.delete_all_bin_files_in_project()


    def test_logged_files_wo_transfer(self):

        # logging without transfer
        file_paths = self.logger.start_logging(
            variables=self.logging_vars, transfer=False, logging_dir=self.logging_dir)
        asyncio.run(asyncio.sleep(0.5))
        self.logger.stop_logging()

        # transfer files from bela
        local_paths = {}
        for var in file_paths["remote_paths"]:
            filename = os.path.basename(file_paths["remote_paths"][var])
            local_paths[var] = self.logger._generate_local_filename(
                os.path.join(self.logging_dir, filename))
            self.logger.copy_file_from_bela(remote_path=file_paths["remote_paths"][var],
                                            local_path=local_paths[var])

        # test logged data
        self._test_logged_data(self.logger, self.logging_vars, local_paths)

        # clean log files
        for var in self.logging_vars:
            remove_file(local_paths[var])
            # self.logger.delete_file_from_bela(
            #     file_paths["remote_paths"][var])
        self.logger.delete_all_bin_files_in_project()



    def test_scheduling_logging(self):
        latest_timestamp = self.logger.get_latest_timestamp()
        sample_rate = self.logger.sample_rate
        timestamps = [latest_timestamp +
                        sample_rate] * len(self.logging_vars)  # start logging after ~1s
        durations = [sample_rate] * len(self.logging_vars)  # log for 1s

        file_paths = self.logger.schedule_logging(variables=self.logging_vars,
                                                    timestamps=timestamps,
                                                    durations=durations,
                                                    transfer=True,
                                                    logging_dir=self.logging_dir)

        self._test_logged_data(self.logger, self.logging_vars,
                                file_paths["local_paths"])

        # clean local log files
        for var in file_paths["local_paths"]:
            if os.path.exists(file_paths["local_paths"][var]):
                os.remove(file_paths["local_paths"][var])
        self.logger.delete_all_bin_files_in_project()

        # # clean all remote log files in project
        # for var in file_paths["remote_paths"]:
        #     self.logger.delete_file_from_bela(
        #         file_paths["remote_paths"][var])



class test_Monitor(unittest.TestCase):
    def setUp(self):
        self.monitor_vars = ["myvar", "myvar2", "myvar3", "myvar4"]
        self.period = 1000
        self.saving_filename = "test_monitor_save.txt"
        self.saving_dir = "./test"

        self.monitor = Monitor()
        self.monitor.connect()

    def tearDown(self):
        self.monitor.__del__()

    def test_peek(self):
        peeked_values = self.monitor.peek()  # peeks at all variables by default
        for var in peeked_values:
            self.assertEqual(peeked_values[var]["timestamp"], peeked_values[var]["value"],
                                "The timestamp of the peeked variable should be equal to the value")

    def test_period_monitor(self):
        self.monitor.start_monitoring(
            variables=self.monitor_vars[:2],
            periods=[self.period]*len(self.monitor_vars[:2]))
        asyncio.run(asyncio.sleep(0.5))
        monitored_values = self.monitor.stop_monitoring()

        for var in self.monitor_vars[:2]:  # assigned at every frame n
            self.assertTrue(np.all(np.diff(monitored_values[var]["timestamps"]) == self.period),
                            "The timestamps of the monitored variables should be spaced by the period")
            if var in ["myvar", "myvar2"]:  # assigned at each frame n
                self.assertTrue(np.all(np.diff(monitored_values[var]["values"]) == self.period),
                                "The values of the monitored variables should be spaced by the period")


    def test_monitor_n_values(self):
        n_values = 25
        monitored_buffer = self.monitor.monitor_n_values(
            variables=self.monitor_vars[:2],
            periods=[self.period]*len(self.monitor_vars[:2]), n_values=n_values)

        for var in self.monitor_vars[:2]:
            self.assertTrue(np.all(np.diff(self.monitor.values[var]["timestamps"]) == self.period),
                            "The timestamps of the monitored variables should be spaced by the period")
            self.assertTrue(np.all(np.diff(self.monitor.values[var]["values"]) == self.period),
                            "The values of the monitored variables should be spaced by the period")
            self.assertTrue(all(len(self.monitor.streaming_buffers_data[
                var]) >= n_values for var in self.monitor_vars[:2]), "The streamed flat buffers for every variable should have at least n_values")
            self.assertTrue(all(len(monitored_buffer[
                var]["values"]) == n_values for var in self.monitor_vars[:2]), "The streaming buffers queue should have n_value for every variable")


    def test_save_monitor(self):

        # delete any existing test files
        for var in self.monitor_vars:
            if os.path.exists(f"{var}_{self.saving_filename}"):
                os.remove(f"{var}_{self.saving_filename}")

        self.monitor.start_monitoring(
            variables=self.monitor_vars,
            periods=[self.period]*len(self.monitor_vars),
            saving_enabled=True,
            saving_filename=self.saving_filename,
            saving_dir=self.saving_dir)
        asyncio.run(asyncio.sleep(0.5))
        monitored_buffers = self.monitor.stop_monitoring()

        for var in self.monitor_vars:
            loaded_buffers = self.monitor.load_data_from_file(os.path.join(self.saving_dir,
                                                                            f"{var}_{self.saving_filename}"))

            self.assertEqual(loaded_buffers["timestamps"], monitored_buffers[var]["timestamps"],
                                "The timestamps of the loaded buffer should be equal to the timestamps of the monitored buffer")
            self.assertEqual(loaded_buffers["values"], monitored_buffers[var]["values"],
                                "The values of the loaded buffer should be equal to the values of the monitored buffer")

        for var in self.monitor_vars:
            remove_file(os.path.join(self.saving_dir,
                                        f"{var}_{self.saving_filename}"))



class test_Controller(unittest.TestCase):
    def setUp(self):
        self.controlled_vars = ["myvar", "myvar2", "myvar3", "myvar4"]

        self.controller = Controller()
        self.controller.connect()

    def tearDown(self):
        self.controller.__del__()

    def test_start_stop_controlling(self):
        self.controller.start_controlling(variables=self.controlled_vars)

        self.assertEqual(self.controller.get_controlled_status(variables=self.controlled_vars), {
                            var: True for var in self.controlled_vars}, "The controlled status of the variables should be True after start_controlling")

        self.controller.stop_controlling(variables=self.controlled_vars)

        self.assertEqual(self.controller.get_controlled_status(variables=self.controlled_vars),  {
                            var: False for var in self.controlled_vars}, "The controlled status of the variables should be False after stop_controlling")


    def test_send_value(self):
        # TODO add streamer to check values are being sent
        self.controller.start_controlling(variables=self.controlled_vars)

        set_value = 4.6

        self.controller.send_value(
            variables=self.controlled_vars, values=[set_value]*len(self.controlled_vars))
        asyncio.run(asyncio.sleep(0.1))  # wait for the values to be set

        _controlled_values = self.controller.get_value(
            variables=self.controlled_vars)  # avoid multiple calls to list

        integer_types = ["i", "j"]
        expected_values = [int(set_value) if self.controller.get_prop_of_var(
            var, "type") in integer_types else set_value for var in self.controlled_vars]

        for idx, var in enumerate(self.controlled_vars):
            self.assertTrue(
                _controlled_values[var] == expected_values[idx], "The controlled value should be 4")



def remove_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)


if __name__ == '__main__':
    # run all tests
    # unittest.main(verbosity=2)

    # select which tests to run
    n = 1
    for i in range(n):

        print(f"\n\n....Running test {i+1}/{n}")

        suite = unittest.TestSuite()
        suite.addTests([
            # watcher
            test_Watcher('test_list'),
            test_Watcher('test_start_stop'),
            # streamer
            test_Streamer('test_stream_n_values'),
            test_Streamer('test_start_stop_streaming'),
            test_Streamer('test_scheduling_streaming'),
            test_Streamer('test_on_buffer_callback'),
            test_Streamer('test_on_block_callback'),
            # logger
            test_Logger('test_logged_files_with_transfer'),
            test_Logger('test_logged_files_wo_transfer'),
            test_Logger('test_scheduling_logging'),
            # monitor
            test_Monitor('test_peek'),
            test_Monitor('test_period_monitor'),
            test_Monitor('test_monitor_n_values'),
            test_Monitor('test_save_monitor'),
            # controller
            test_Controller('test_start_stop_controlling'),
            test_Controller('test_send_value')
        ])
        # suite.addTest(test_Streamer('test_on_block_callback'))
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
