import os
import asyncio
import aiofiles
import struct
from .Watcher import Watcher
from .utils import _print_error, _print_info, _print_ok, _print_warning


class Logger(Watcher):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Logger class

            Args:
                ip (str, optional): Remote address IP. If using internet over USB, the IP won't work, pass "bela.local". Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """
        super(Logger, self).__init__(ip, port, data_add, control_add)

        self._logging_mode = "OFF"
        self._logging_vars = []
        self._logging_transfer = True

        self._active_copying_tasks = []

        self._mode = "LOG"

    # -- logging methods --

    def is_logging(self):
        """ Returns True if the logger is currently logging, false otherwise.

        Returns:
            bool: Logger status
        """
        return True if self._logging_mode != "OFF" else False

    def start_logging(self, variables=[], transfer=True, logging_dir="./"):
        """ Starts logging session. The session can be ended by calling stop_logging().

        Args:
            variables (list of str, optional): List of variables to be logged. If no variables are passed, all variables in the watcher are logged. Defaults to [].
            transfer (bool, optional): If True, the logged files will be transferred automatically during the logging session. Defaults to False. #FIXME too slow

        Returns:
            list of str: List of local paths to the logged files.
        """
        remote_paths = self.loop.run_until_complete(self.__async_logging_common_routine(
            mode="FOREVER", timestamps=[], durations=[], variables=variables, logging_dir=logging_dir))

        local_paths = {}
        if transfer:
            self.connect_ssh()  # start ssh connection
            for var in [v for v in self.watcher_vars if v["name"] in variables]:
                var = var["name"]
                local_path = os.path.join(
                    logging_dir, os.path.basename(remote_paths[var]))

                # if file already exists, throw a warning and add number at the end of the filename
                local_paths[var] = self._generate_local_filename(
                    local_path)

                copying_task = self.__copy_file_in_chunks(
                    remote_paths[var], local_paths[var])
                self._active_copying_tasks.append(copying_task)

        return {"local_paths": local_paths, "remote_paths": remote_paths}

    def schedule_logging(self, variables=[], timestamps=[], durations=[], transfer=True, logging_dir="./"):
        """Schedule logging session. The session starts at the specified timestamps and lasts for the specified durations. If the timestamp is in the past, the logging will start immediately. The session can be ended by calling stop_logging().

        Args:
            variables (list, optional): Variables to be logged. Defaults to [].
            timestamps (list, optional): Timestamps to start logging (one for each variable). Defaults to [].
            durations (list, optional): Durations to log for (one for each variable). Defaults to [].
            transfer (bool, optional): Transfer files to laptop automatically during logging session. Defaults to True.
            logging_dir (str, optional): Path to store the files. Defaults to "./".
        """

        # check timestamps and duration types
        assert isinstance(
            timestamps, list) and all(isinstance(timestamp, int) for timestamp in timestamps), "Error: timestamps must be a list of ints."
        assert isinstance(
            durations, list) and all(isinstance(duration, int) for duration in durations), "Error: durations must be a list of ints."

        remote_paths = self.loop.run_until_complete(self.__async_logging_common_routine(
            mode="SCHEDULED", timestamps=timestamps, durations=durations, variables=variables, logging_dir=logging_dir))

        async def _async_schedule_logging(variables, timestamps, durations, transfer, logging_dir):
            # checks types and if no variables are specified, stream all watcher variables (default)
            latest_timestamp = await self._async_get_latest_timestamp()

            local_paths = {}
            if transfer:
                self.connect_ssh()  # start ssh connection

                async def _async_check_if_file_exists_and_start_copying(var, timestamp):

                    diff_stamps = timestamp - latest_timestamp
                    while True:
                        _has_file_been_created = 0

                        remote_file_size = self.sftp_client.stat(
                            remote_paths[var]).st_size

                        if remote_file_size > 0:  # white till first buffers are written into the file
                            _has_file_been_created = 1
                            _print_info(
                                f"Logging started for {var}...")
                            break  # Break the loop if the remote file size is non-zero

                        if _has_file_been_created:
                            break

                        # Wait before checking again
                        await asyncio.sleep(diff_stamps//(2*self.sample_rate))

                    # when file has been created
                    local_path = os.path.join(
                        logging_dir, os.path.basename(remote_paths[var]))

                    # if file already exists, throw a warning and add number at the end of the filename
                    local_paths[var] = self._generate_local_filename(
                        local_path)

                    copying_task = self.__copy_file_in_chunks(
                        remote_paths[var], local_paths[var])
                    self._active_copying_tasks.append(copying_task)

                _active_checking_tasks = []
                for idx, var in enumerate(variables):
                    check_task = self.loop.create_task(
                        _async_check_if_file_exists_and_start_copying(var, timestamps[idx]))
                    _active_checking_tasks.append(check_task)

                # wait for the longest duration
                await asyncio.sleep(max(durations)//(self.sample_rate))
                self._logging_mode = "OFF"

                # wait for all the files to be created
                await asyncio.gather(*_active_checking_tasks, return_exceptions=True)
                # wait for all the files to be copied
                await asyncio.gather(*self._active_copying_tasks, return_exceptions=True)
                self._active_copying_tasks.clear()
                _active_checking_tasks.clear()
                if self.sftp_client:
                    self.disconnect_ssh()

                # async version (non blocking)
                # async def _async_cleanup():
                #     await asyncio.gather(*self._active_copying_tasks, return_exceptions=True)
                #     self._active_copying_tasks.clear()
                #     self.sftp_client.close()
                # asyncio.run(_async_cleanup())

            return {"local_paths": local_paths, "remote_paths": remote_paths}

        return self.loop.run_until_complete(_async_schedule_logging(variables=variables, timestamps=timestamps, durations=durations, transfer=transfer, logging_dir=logging_dir))

    async def __async_logging_common_routine(self, mode, timestamps=[], durations=[], variables=[], logging_dir="./"):
        # checks types and if no variables are specified, stream all watcher variables (default)
        variables = self._var_arg_checker(variables)

        if not os.path.exists(logging_dir):
            os.makedirs(logging_dir)

        if self.is_logging():
            self.loop.create_task(self._async_stop_logging())

        # self.connect_ssh()  # start ssh connection

        self._logging_mode = mode

        remote_files, remote_paths = {}, {}

        await self._async_send_ctrl_msg({"watcher": [
            {"cmd": "log", "timestamps": timestamps, "durations": durations, "watchers": variables}]})

        _list = await self._async_list()
        for idx, var in enumerate(variables):
            remote_files[var] = _list["watchers"][idx]["logFileName"]
            remote_paths[var] = f'/root/Bela/projects/{self.project_name}/{remote_files[var]}'

        _print_info(
            f"Started logging variables {variables}... Run stop_logging() to stop logging.")

        return remote_paths

    async def _async_stop_logging(self, variables=[]):
        """Stops logging session.

        Args:
            variables (list of str, optional): List of variables to stop logging. If none is passed, logging is stopped for all variables in the watcher. Defaults to [].
        """
        self._logging_mode = "OFF"
        if variables == []:
            # if no variables specified, stop streaming all watcher variables (default)
            variables = [var["name"] for var in self.watcher_vars]

        await self._async_send_ctrl_msg(
            {"watcher": [{"cmd": "unlog", "watchers": variables}]})

        _print_info(f"Stopped logging variables {variables}...")

        await asyncio.gather(*self._active_copying_tasks, return_exceptions=True)
        self._active_copying_tasks.clear()
        if self.sftp_client:
            self.disconnect_ssh()

    def stop_logging(self, variables=[]):
        """ Stops logging session. Sync wrapper for _async_stop_logging().

        Args:
            variables (list of str, optional): List of variables to stop logging. If none is passed, logging is stopped for all variables in the watcher. Defaults to [].
        """

        return self.loop.run_until_complete(self._async_stop_logging(variables))

    # -- binary file parsing method

    def read_binary_file(self, file_path, timestamp_mode):
        """ Reads a binary file generated by the logger and returns a dictionary with the file contents.

        Args:
            file_path (str): Path of the file to be read.
            timestamp_mode (str): Timestamp mode of the variable. Can be "dense" or "sparse".

        Returns:
            dict: Dictionary with the file contents.
        """
        if file_path is None:
            _print_error("Error: No file path provided.")
            return
        file_size = os.path.getsize(file_path)
        assert file_size != 0, f"Error: The size of {file_path} is 0."

        def _parse_null_terminated_string(file):
            result = ""
            while True:
                char = file.read(1).decode('utf-8')
                if char == '\0':
                    break
                result += char
            return result

        with open(file_path, "rb") as file:

            # parse header
            name = _parse_null_terminated_string(file)
            var_name = _parse_null_terminated_string(file)
            _type = _parse_null_terminated_string(file)
            pid = struct.unpack("I", file.read(struct.calcsize("I")))[0]
            pid_id = struct.unpack("I", file.read(struct.calcsize("I")))[0]

            # if header size is not a multiple of 4, we need to add padding
            header_size = len(name) + len(var_name) + len(_type) + \
                3 + struct.calcsize("I") + struct.calcsize("I")
            if header_size % 4 != 0:
                file.read(4 - header_size % 4)  # padding

            _parse_type = 'i' if _type == 'j' else _type  # struct does not understand 'j'

            # parse data buffers
            parsed_buffers = []
            while True:
                # Read file buffer by buffer
                try:
                    data = file.read(self.get_buffer_size(
                        _parse_type, timestamp_mode))
                    if len(data) == 0:
                        break  # No more data to read
                    _parsed_buffer = self._parse_binary_data(
                        data, timestamp_mode, _parse_type)
                    parsed_buffers.append(_parsed_buffer)

                except struct.error as e:
                    _print_error(str(e))
                    break  # No more data to read

        return {
            "project_name": name,
            "var_name": var_name,
            "type": _type,
            # "pid": pid,
            # "pid_id": pid_id,
            "buffers": parsed_buffers
        }

    # -- file transfer utils --
    # expand copy_file_from_bela method in Watcher

    def __copy_file_in_chunks(self, remote_path, local_path,  chunk_size=2**12):
        """ Copies a file from the remote path to the local path in chunks. This function is called by start_logging() if transfer=True.

        Args:
            remote_path (str): Path to the file in Bela.
            local_path (str): Path to the file in the local machine (where the file is copied to)
            chunk_size (int, optional): Chunk size. Defaults to 2**12.

        Returns:
            asyncio.Task: Task that copies the file in chunks.
        """

        async def async_copy_file_in_chunks(remote_path, local_path, chunk_size=2**12):

            while True:
                # Wait for a second before checking again
                await asyncio.sleep(1)  # TODO can this be lower?

                try:
                    remote_file = self.sftp_client.open(remote_path, 'rb')
                    remote_file_size = self.sftp_client.stat(
                        remote_path).st_size

                    if remote_file_size > 0:  # white till first buffers are written into the file
                        break  # Break the loop if the remote file size is non-zero

                except FileNotFoundError:
                    _print_error(
                        f"Remote file '{remote_path}' does not exist.")
                    return None

            try:
                async with aiofiles.open(local_path, 'wb') as local_file:
                    while True:
                        chunk = remote_file.read(chunk_size)
                        # keep checking file whilst logging is still going on (in case a variable fills the buffers slowly)
                        if not chunk and self._logging_mode == "OFF":
                            await asyncio.sleep(0.1)  # flushed data
                            break
                        await local_file.write(chunk)
                        _print_ok(
                            f"\rTransferring {remote_path}-->{local_path}...", end="", flush=True)
                        await asyncio.sleep(0.1)
                    chunk = remote_file.read()
                    if chunk:
                        await local_file.write(chunk)
                    remote_file.close()
                    _print_ok("Done.")

            except Exception as e:
                _print_error(
                    f"Error while transferring file: {e}.")
                return None

            finally:
                await self._async_remove_item_from_list(self._active_copying_tasks, asyncio.current_task())

        return self.loop.create_task(async_copy_file_in_chunks(remote_path, local_path, chunk_size))

    def copy_all_bin_files_in_project(self, dir="./", verbose=True):
        """ Copies all .bin files in the specified remote directory using SFTP.

        Args:
            dir (str, optional): Path to the local directory where the files are copied to. Defaults to "./".
            verbose (bool, optional): Show info messages. Defaults to True.
        """
        remote_path = f'/root/Bela/projects/{self.project_name}'
        try:
            self.connect_ssh()
            copy_tasks = self._action_on_all_bin_files_in_project(
                "copy", dir)

            # wait until all files are copied
            self.loop.run_until_complete(asyncio.gather(
                *copy_tasks, return_exceptions=True))

            if verbose:
                _print_ok(
                    f"All .bin files in {remote_path} have been copied to {dir}.")
        except Exception as e:
            _print_error(
                f"Error copying .bin files in {remote_path}: {e}")
        finally:
            self.disconnect_ssh()

    def finish_copying_file(self, remote_path, local_path):  # TODO test
        """Finish copying file if it was interrupted. This function is used to copy the remaining part of a file that was interrupted during the copy process.

        Args:
           remote_path (str): Path to the file in Bela.
            local_path (str): Path to the file in the local machine (where the file is copied to)
        """
        self.connect_ssh()

        try:
            remote_file = self.sftp_client.open(remote_path, 'rb')
            remote_file_size = self.sftp_client.stat(
                remote_path).st_size
        except FileNotFoundError:
            _print_error(
                f"Remote file '{remote_path}' does not exist.")
            self.disconnect_ssh()
            return None
        if not os.path.exists(local_path):
            _print_error(
                f"Local file '{local_path}' does not exist. If you want to copy a file that hasn't been partially copied yet, use copy_file_from_bela() instead.")
            self.disconnect_ssh()
            return None
        local_file_size = os.path.getsize(local_path)

        try:
            if local_file_size < remote_file_size:
                # Calculate the remaining part to copy
                remaining_size = remote_file_size - local_file_size
                # Use readv to read the remaining part of the file
                chunks = [(local_file_size, remaining_size)]
                data = remote_file.readv(chunks)

                _print_ok(
                    f"\rTransferring {remote_path}-->{local_path}...", end="", flush=True)
                # Append the data to the local file
                with open(local_path, 'ab') as local_file:
                    local_file.write(data)
                _print_ok("Done.")
            else:
                _print_error(
                    "Local file is already up-to-date or larger than the remote file.")
        except Exception as e:
            _print_error(f"Error finishing file copy: {e}")

        self.disconnect_ssh()

    def delete_file_from_bela(self, remote_path, verbose=True):
        """Deletes a file from the remote path in Bela.

        Args:
            remote_path (str): Path to the remote file to be deleted. 
        """
        self.connect_ssh()
        self.loop.run_until_complete(
            self._async_delete_file_from_bela(remote_path, verbose))
        self.disconnect_ssh()

    def delete_all_bin_files_in_project(self, verbose=True):
        """ Deletes all .bin files in the specified remote directory using SFTP.
        """
        remote_path = f'/root/Bela/projects/{self.project_name}'
        try:
            self.connect_ssh()
            deletion_tasks = self._action_on_all_bin_files_in_project(
                "delete")

            # wait until all files are deleted
            self.loop.run_until_complete(asyncio.gather(
                *deletion_tasks, return_exceptions=True))

            if verbose:
                _print_ok(
                    f"All .bin files in {remote_path} have been removed.")
        except Exception as e:
            _print_error(
                f"Error deleting .bin files in {remote_path}: {e}")
        finally:
            self.disconnect_ssh()

    async def _async_delete_file_from_bela(self, remote_path, verbose=True):
        # this function doesn't return until the file has been deleted
        try:
            self.sftp_client.stat(remote_path)  # check if file exists
        except FileNotFoundError:
            _print_error(
                f"Error: Remote file '{remote_path}' does not exist.")
            return

        while True:
            await asyncio.sleep(0.1)  # Adjust the interval as needed
            try:
                # Attempt to remove the file
                self.sftp_client.remove(remote_path)
            except FileNotFoundError:
                # File does not exist, it has been successfully removed
                if verbose:
                    _print_ok(
                        f"File '{remote_path}' has been removed from Bela.")
                break
            except Exception as e:
                _print_error(
                    f"Error while deleting file in Bela: {e} ")
                break

    def _action_on_all_bin_files_in_project(self, action, local_dir=None):
        # List all files in the remote directory
        remote_path = f'/root/Bela/projects/{self.project_name}'
        file_list = self.sftp_client.listdir(remote_path)
        if len(file_list) == 0:
            _print_warning(f"No .bin files in {remote_path}.")
            return

        # Iterate through the files and delete .bin files
        tasks = []

        for file_name in file_list:
            if file_name.endswith('.bin'):
                remote_file_path = f"{remote_path}/{file_name}"
                if action == "delete":
                    task = self.loop.create_task(
                        self._async_delete_file_from_bela(remote_file_path))
                elif action == "copy":
                    local_filename = os.path.join(local_dir, file_name)
                    task = self.loop.create_task(
                        self._async_copy_file_from_bela(remote_file_path, local_filename))
                else:
                    raise ValueError(f"Invalid action: {action}")
                tasks.append(task)

        return tasks

    def __del__(self):
        super().__del__()
        self.disconnect_ssh()  # disconnect ssh
