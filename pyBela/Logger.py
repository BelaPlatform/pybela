import paramiko
import aiofiles
import asyncio
import os
from .Watcher import Watcher


class Logger(Watcher):
    def __init__(self, ip="192.168.7.2", port=5555, data_add="gui_data", control_add="gui_control"):
        """ Logger class

            Args:
                ip (str, optional): Remote address IP. Defaults to "192.168.7.2".
                port (int, optional): Remote address port. Defaults to 5555.
                data_add (str, optional): Data endpoint. Defaults to "gui_data".
                control_add (str, optional): Control endpoint. Defaults to "gui_control".
        """
        super(Logger, self).__init__(ip, port, data_add, control_add)

        self._logging = False
        self._logging_vars = []
        self._logging_transfer = True
        self._logging_filename = "var_logging.txt"

        self.ssh_client = None
        self.sftp_client = None

        self._active_copying_tasks = []

    def start_logging(self, variables=[], transfer=True, saving_filename="var_logging.txt"):

        # TODO allow custom filenaming?

        if len(variables) == 0:
            # if no variables are specified, stream all watcher variables (default)
            variables = [var["name"] for var in self.watcher_vars]
        variables = variables if isinstance(variables, list) else [
            variables]  # variables should be a list of strings

        if self.is_logging():
            self.stop_logging()

        self.start()  # start websocket connection
        self.connect_ssh()  # start ssh connection

        self._logging = True

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "log", "watchers": variables}]})

        if transfer:
            local_paths = {}
            for var in [v for v in self.watcher_vars if v["name"] in variables]:
                remote_path = f"/root/Bela/projects/{self._project_name}/{var['log_filename']}"
                _local_path = var["log_filename"]

                if os.path.exists(_local_path):
                    local_dir = os.path.dirname(_local_path)
                    local_base = os.path.basename(_local_path)
                    base_name, ext = os.path.splitext(local_base)
                    local_path = os.path.join(local_dir, f"{base_name}_2{ext}")
                    counter = 2
                    while os.path.exists(local_path):
                        counter += 1
                        local_path = os.path.join(
                            local_dir, f"{base_name}_{counter}{ext}")
                else:
                    local_path = _local_path

                local_paths[var["name"]] = local_path

                copying_task = asyncio.create_task(
                    self.async_copy_file_in_chunks(remote_path, local_path))
                self._active_copying_tasks.append(copying_task)

            return local_paths

    async def async_stop_logging(self, variables=[]):

        self._logging = False
        if variables == []:
            # if no variables specified, stop streaming all watcher variables (default)
            variables = [var["name"] for var in self.watcher_vars]

        self.send_ctrl_msg(
            {"watcher": [{"cmd": "unlog", "watchers": variables}]})

        await asyncio.gather(*self._active_copying_tasks, return_exceptions=True)
        self._active_copying_tasks.clear()

        self.stop()

    def stop_logging(self, variables=[]):
        return asyncio.run(self.async_stop_logging(variables))

    def connect_ssh(self):
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

    def is_logging(self):
        return self._logging

    async def async_copy_file_in_chunks(self, remote_path, local_path, chunk_size=2**12):
        try:
            remote_file = self.sftp_client.open(remote_path, 'rb')
        except FileNotFoundError:
            print(f"Remote file '{remote_path}' does not exist.")
            return

        local_size = os.path.getsize(
            local_path) if os.path.exists(local_path) else 0

        try:
            async with aiofiles.open(local_path, 'wb') as local_file:
                # Move the remote file pointer to the last position read
                remote_file.seek(local_size)
                while True:
                    chunk = remote_file.read(chunk_size)
                    if not chunk:
                        print("\nTransfer successful")
                        break
                    await local_file.write(chunk)
                    print(
                        f"\rTransferring {remote_path}-->{local_path}... ", end="", flush=True)

                remote_file.close()
                self.sftp_client.close()

        except Exception as e:
            print(f"Error while transferring file: {e}")
            return None

    def copy_file_in_chunks(self, remote_path, local_path):
        return asyncio.run(self.async_copy_file_in_chunks(remote_path, local_path))

    def copy_file_from_bela(self, remote_path, local_path):
        if self.sftp_client is None:
            self.connect_ssh()
        self.sftp_client.get(remote_path, local_path)
