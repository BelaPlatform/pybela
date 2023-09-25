import os
import warnings
import asyncio
import aiofiles
import struct
import paramiko
from .Watcher import Watcher


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

        self._logging = False
        self._logging_vars = []
        self._logging_transfer = True

        self.ssh_client = None
        self.sftp_client = None

        self._active_copying_tasks = []

        self._mode = "LOG"

    def start_logging(self, variables=[], transfer=True, dir="./"):
        """ Starts logging session. The session can be ended by calling stop_logging().

        Args:
            variables (list of str, optional): List of variables to be logged. If no variables are passed, all variables in the watcher are logged. Defaults to [].
            transfer (bool, optional): If True, the logged files will be transferred automatically during the logging session. Defaults to True.

        Returns:
            list of str: List of local paths to the logged files.
        """

        # checks types and if no variables are specified, stream all watcher variables (default)
        variables = self._var_arg_checker(variables)

        if not os.path.exists(dir):
            os.makedirs(dir)

        if self.is_logging():
            self.stop_logging()

        # self.start()  # start websocket connection -- done with .connect()
        self.connect_ssh()  # start ssh connection

        self._logging = True

        async def _async_send_logging_cmd_and_wait_for_response(var):
            # the logger responds with the name of the file where the variable is being logged in Bela
            # the logger responds with one message per variable -- so to keep track of responses it is easier to ask for a variable at a time rather than all at once
            self.send_ctrl_msg(
                {"watcher": [{"cmd": "log", "watchers": [var]}]})
            await self._log_response_available.wait()
            self._log_response_available.clear()
            return self._log_response

        remote_files = {}
        remote_paths = {}
        for var in variables:
            remote_files[var] = asyncio.run(_async_send_logging_cmd_and_wait_for_response(var))[
                "logFileName"]
            remote_paths[var] = f'/root/Bela/projects/{self.project_name}/{remote_files[var]}'

        if transfer:
            local_paths = {}
            for var in [v for v in self.watcher_vars if v["name"] in variables]:
                var = var["name"]
                local_path = os.path.join(dir, remote_files[var])

                # if file already exists, throw a warning and add number at the end of the filename
                if os.path.exists(local_path):
                    base, ext = os.path.splitext(local_path)
                    counter = 1
                    new_local_path = local_path
                    while os.path.exists(new_local_path):
                        new_local_path = f"{base}_{counter}{ext}"
                        counter += 1
                    warnings.warn(
                        f"\n\033[91m{local_path} already exists. Renaming file to {new_local_path}\033[0m\n")

                    local_path = new_local_path

                local_paths[var] = local_path

                copying_task = self.copy_file_in_chunks(
                    remote_paths[var], local_path)
                self._active_copying_tasks.append(copying_task)

            return {"local_paths": local_paths, "remote_paths": remote_paths}
        return {"remote_paths": remote_paths}

    def stop_logging(self, variables=[]):
        """ Stops logging session.

        Args:
            variables (list of str, optional): List of variables to stop logging. If none is passed, logging is stopped for all variables in the watcher. Defaults to [].
        """
        async def async_stop_logging(variables=[]):
            self._logging = False
            if variables == []:
                # if no variables specified, stop streaming all watcher variables (default)
                variables = [var["name"] for var in self.watcher_vars]

            self.send_ctrl_msg(
                {"watcher": [{"cmd": "unlog", "watchers": variables}]})

            await asyncio.gather(*self._active_copying_tasks, return_exceptions=True)
            self._active_copying_tasks.clear()

            self.sftp_client.close()

            # self.stop()

        return asyncio.run(async_stop_logging(variables))

    def connect_ssh(self):
        """ Connects to Bela via ssh to transfer log files.
        """
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Workaround for no authentication:
        # https://github.com/paramiko/paramiko/issues/890#issuecomment-906893725
        try:
            self.ssh_client.connect(
                self.ip, port=22, username="root", password=None)
        except paramiko.SSHException as e:
            self.ssh_client.get_transport().auth_none("root")

        self.sftp_client = self.ssh_client.open_sftp()  # TODO handle exceptions better

    def disconnect_ssh(self):
        """ Disconnects from Bela via ssh.
        """
        self.sftp_client.close()
        self.ssh_client.close()

    def is_logging(self):
        """ Returns True if the logger is currently logging, false otherwise.

        Returns:
            bool: Logger status
        """
        return self._logging

    def copy_file_in_chunks(self, remote_path, local_path,  chunk_size=2**12):
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
                await asyncio.sleep(1)

                try:
                    remote_file = self.sftp_client.open(remote_path, 'rb')
                    remote_file_size = self.sftp_client.stat(
                        remote_path).st_size

                    if remote_file_size > 0:  # white till first buffers are written into the file
                        break  # Break the loop if the remote file size is non-zero

                except FileNotFoundError:
                    print(f"Remote file '{remote_path}' does not exist.")
                    return None

            try:
                async with aiofiles.open(local_path, 'wb') as local_file:
                    while True:
                        chunk = remote_file.read(chunk_size)
                        if not chunk:
                            break
                        await local_file.write(chunk)
                        print(
                            f"\rTransferring {remote_path}-->{local_path}... ", end="", flush=True)
                    remote_file.close()
                    print("Done.")

            except Exception as e:
                print(f"Error while transferring file: {e}")
                return None

            finally:
                await self._async_remove_item_from_list(self._active_copying_tasks, asyncio.current_task())

        return asyncio.create_task(async_copy_file_in_chunks(remote_path, local_path, chunk_size))

    def read_binary_file(self, file_path, timestamp_mode):
        # FIXME does not work for n logging sessions because header does not exist. either discard header or add it to the file -- force logger to persist
        """ Reads a binary file generated by the logger and returns a dictionary with the file contents.

        Args:
            file_path (str): Path of the file to be read.
            timestamp_mode (str): Timestamp mode of the variable. Can be "dense" or "sparse". 

        Returns:
            dict: Dictionary with the file contents.
        """

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
                    print(e)
                    break  # No more data to read

        return {
            "project_name": name,
            "var_name": var_name,
            "type": _type,
            # "pid": pid,
            # "pid_id": pid_id,
            "buffers": parsed_buffers
        }

    # - utils

    # -- ssh copy utils

    def copy_file_from_bela(self, remote_path, local_path, verbose=False):
        self.connect_ssh()
        asyncio.run(self._async_copy_file_from_bela(
            remote_path, local_path, verbose))
        self.disconnect_ssh()

    def copy_all_bin_files_in_project(self, dir="./", verbose=False):
        """ Copies all .bin files in the specified remote directory using SFTP.
        """
        self.connect_ssh()
        remote_path = f'/root/Bela/projects/{self.project_name}'
        try:
            copy_tasks = self._action_on_all_bin_files_in_project(
                "copy", dir)

            # wait until all files are copied
            asyncio.run(asyncio.gather(
                *copy_tasks, return_exceptions=True))

            if verbose:
                print(
                    f"All .bin files in {remote_path} have been copied to {dir}.")
        except Exception as e:
            print(f"Error copying .bin files in {remote_path}: {e}")
        finally:
            self.disconnect_ssh()

    async def _async_copy_file_from_bela(self, remote_path, local_path, verbose=False):
        """ Copies a file from the remote path in Bela to the local path. This can be used any time to copy files from Bela to the host. 

        Args:
            remote_path (str): Path to the file in Bela.
            local_path (str): Path to the file in the local machine (where the file is copied to)
        """
        # TODO add warining if file exists
        try:
            transferred_event = asyncio.Event()
            def callback(transferred, to_transfer): return transferred_event.set(
            ) if transferred == to_transfer else None
            self.sftp_client.get(remote_path, local_path, callback=callback)
            await asyncio.wait_for(transferred_event.wait(), timeout=3)
            if verbose:
                print(f"\rTransferring {remote_path}-->{local_path}... Done.")
            return transferred_event.is_set()
        except asyncio.TimeoutError:
            print("Timeout while transferring file.")
            return False  # File copy did not complete within the timeout
        except Exception as e:
            print(f"Error while transferring file: {e}")
            return False

    # -- ssh delete utils

    def delete_file_from_bela(self, remote_path, verbose=False):
        """Deletes a file from the remote path in Bela.

        Args:
            remote_path (str): Path to the remote file to be deleted. 
        """
        self.connect_ssh()
        asyncio.run(self._async_delete_file_from_bela(remote_path, verbose))
        self.disconnect_ssh()

    def delete_all_bin_files_in_project(self, verbose=False):
        """ Deletes all .bin files in the specified remote directory using SFTP.
        """
        self.connect_ssh()
        try:
            deletion_tasks = self._action_on_all_bin_files_in_project(
                "delete")

            # wait until all files are deleted
            asyncio.run(asyncio.gather(
                *deletion_tasks, return_exceptions=True))

            remote_path = f'/root/Bela/projects/{self.project_name}'
            if verbose:
                print(
                    f"All .bin files in {remote_path} have been removed.")
        except Exception as e:
            print(f"Error deleting .bin files in {remote_path}: {e}")
        finally:
            self.disconnect_ssh()

    async def _async_delete_file_from_bela(self, remote_path, verbose=False):
        # this function doesn't return until the file has been deleted
        while True:
            await asyncio.sleep(0.1)  # Adjust the interval as needed
            try:
                # Attempt to remove the file
                self.sftp_client.remove(remote_path)
            except FileNotFoundError:
                # File does not exist, it has been successfully removed
                if verbose:
                    print(f"File '{remote_path}' has been removed from Bela.")
                break
            except Exception as e:
                print(f"Error while deleting file in Bela: {e}")
                break

    # -- bunk task utils

    def _action_on_all_bin_files_in_project(self, action, local_dir=None):
        # List all files in the remote directory
        remote_path = f'/root/Bela/projects/{self.project_name}'
        file_list = self.sftp_client.listdir(remote_path)
        if len(file_list) == 0:
            print(f"No .bin files in {remote_path}.")
            return

        # Iterate through the files and delete .bin files
        tasks = []
        for file_name in file_list:
            if file_name.endswith('.bin'):
                remote_file_path = f"{remote_path}/{file_name}"
                if action == "delete":
                    task = asyncio.create_task(
                        self._async_delete_file_from_bela(remote_file_path))
                elif action == "copy":
                    local_filename = os.path.join(local_dir, file_name)
                    task = asyncio.create_task(
                        self._async_copy_file_from_bela(remote_file_path, local_filename))
                else:
                    raise ValueError(f"Invalid action: {action}")
                tasks.append(task)

        return tasks
