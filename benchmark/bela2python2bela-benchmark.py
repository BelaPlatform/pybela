from pybela import Streamer
import numpy as np
from datetime import datetime
import csv

buffer_length = 1024

# when the streamer receives a buffer, it calls this function
# and passes the buffer as an argument


async def callback(buffer, streamer):
    # diff frames elapsed from previous buffer
    diffFramesElapsed = buffer['buffer']['data'][0]
    diffs.append(diffFramesElapsed)

    buffer_id, buffer_type = 0, 'i'
    data_list = np.zeros(buffer_length, dtype=int)
    ref_timestamp = buffer['buffer']['ref_timestamp']
    data_list[0] = ref_timestamp
    streamer.send_buffer(buffer_id, buffer_type, buffer_length, data_list)


if __name__ == "__main__":
    streamer = Streamer()
    streamer.connect()
    streamer.connect_ssh()

    vars, diffs = ['auxWatcherVar'], []

    cpu_logs_bela_path = f"/root/Bela/projects/{streamer.project_name}/cpu-logs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format: YYYYMMDD_HHMMSS
    cpu_logs_filename = f"{timestamp}_cpu-load.log"

    streamer.ssh_client.exec_command(f"mkdir -p {cpu_logs_bela_path}")

    #  < -- streaming starts -- >

    streamer.start_streaming(vars, on_buffer_callback=callback, callback_args=(streamer))

    # start cpu monitoring
    streamer.ssh_client.exec_command(
        f"node /root/Bela/IDE/dist/bela-cpu.js >  {cpu_logs_bela_path}/{cpu_logs_filename} 2>&1 &")

    # watcher is ticking inside binaryDataCallback so we need to send data to get it started
    buffer_id, buffer_type, _zeros = 0, 'i', np.zeros(buffer_length, dtype=int)
    streamer.send_buffer(buffer_id, buffer_type, buffer_length, _zeros)  # send zeros buffer to get it started

    # stream for n seconds
    streamer.wait(30)

    # kill cpu monitoring
    streamer.ssh_client.exec_command("pkill -f 'node /root/Bela/IDE/dist/bela-cpu.js'")

    streamer.stop_streaming()

    #  < -- streaming finishes -- >

    # cpu-logs legend: MSW, CPU usage, audio thread CPU usage
    streamer.copy_file_from_bela(f"{cpu_logs_bela_path}/{cpu_logs_filename}", f"benchmark/data/{cpu_logs_filename}")
    # save diffs locally

    # drop first value (it is the time it takes to receive the first buffer), use np.array to allow element-wise operations
    diffs = np.array(diffs[1:])
    diffs_in_ms = np.round(diffs*1000/streamer.sample_rate, 1)  # 1 dec. position

    with open(f"benchmark/data/{timestamp}-diffs.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(diffs_in_ms)

    avg_roundtrip = np.round(np.average(diffs_in_ms), 2)  # discard first value
    print("average roundtrip ", avg_roundtrip, "ms ; num of buffers received: ", len(diffs))
