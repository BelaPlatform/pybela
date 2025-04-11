from pybela import Streamer
import numpy as np
import csv
import argparse

BUFFER_LENGTH = 1024
TIME_INTERVAL = 30
NUM_AUX_VARIABLES = 1


async def callback(buffer, streamer):
    """when the streamer receives a buffer, it calls this function and passes the buffer as an argument"""
    # diff frames elapsed from previous buffer
    _var = buffer['name']
    diffFramesElapsed = buffer['buffer']['data'][0]
    diffs[_var].append(diffFramesElapsed)

    ref_timestamp = buffer['buffer']['ref_timestamp']
    frames[_var].append(ref_timestamp)

    buffer_id, buffer_type = vars.index(_var), 'i'
    data_list = np.zeros(BUFFER_LENGTH, dtype=int)
    data_list[0] = ref_timestamp
    streamer.send_buffer(buffer_id, buffer_type, BUFFER_LENGTH, data_list)


def save_to_csv(var_to_save, filename):
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)

        writer.writerow(vars)

        max_len = max(len(var_to_save[_var]) for _var in vars)
        for i in range(max_len):
            row = []
            for _var in vars:
                # Add timestamp and diff if available, otherwise add empty values
                if i < len(var_to_save[_var]):
                    row.extend([var_to_save[_var][i]])
                else:
                    row.extend([""])  # Fill with empty strings if data is missing
            writer.writerow(row)


if __name__ == "__main__":

    # argument parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("--rfn", type=str, default="", help="root file name")
    parser.add_argument("--time", type=int, default=30, help="time interval in seconds")
    parser.add_argument("--numAuxVars", type=int, default=1, help="number of aux variables")

    args = parser.parse_args()
    root_filename = args.rfn
    TIME_INTERVAL = args.time
    NUM_AUX_VARIABLES = args.numAuxVars

    streamer = Streamer()
    streamer.connect()
    streamer.connect_ssh()

    vars = [f'auxWatcherVar{idx}' for idx in range(NUM_AUX_VARIABLES)]
    diffs, frames = {var: [] for var in vars}, {var: [] for var in vars}

    cpu_logs_bela_path = f"/root/Bela/projects/{streamer.project_name}/cpu-logs"
    cpu_logs_filename = f"{root_filename}_cpu-load.log"

    #  < -- streaming starts -- >

    streamer.start_streaming(vars, on_buffer_callback=callback, callback_args=(streamer))

    # start cpu monitoring
    print("Starting Bela-CPU monitoring...")

    # truncate cpu logs file
    streamer.ssh_client.exec_command(f"echo '' > {cpu_logs_bela_path}/{cpu_logs_filename}")

    # watcher is ticking inside binaryDataCallback so we need to send data to get it started
    buffer_type, _zeros = 'i', np.zeros(BUFFER_LENGTH, dtype=int)
    for idx in range(NUM_AUX_VARIABLES):
        streamer.send_buffer(idx, buffer_type, BUFFER_LENGTH, _zeros)  # send zeros buffer to get it started

    # stream for n seconds
    streamer.wait(TIME_INTERVAL)

    streamer.stop_streaming()

    #  < -- streaming finishes -- >

    diffs_in_ms = {}
    sr = streamer.sample_rate
    for _var in vars:
        # calc diff in ms for each var
        # drop first value (it is the time it takes to receive the first buffer), use np.array to allow element-wise operations
        diffs[_var], frames[_var] = np.array(diffs[_var][1:]), np.array(frames[_var][1:])
        diffs_in_ms[_var] = np.round(diffs[_var]*1000/sr, 1)  # 1 dec. position

        # print average roundtrip for each var
        avg_roundtrip = np.round(np.average(diffs_in_ms[_var]), 2)  # discard first value
        print(f"{_var} -- average roundtrip {avg_roundtrip} ms ; num of buffers received: {len(diffs[_var])}")

    # save diffs to csv
    save_to_csv(diffs_in_ms, f"benchmark/data/{root_filename}_diffs.csv")
    save_to_csv(frames, f"benchmark/data/{root_filename}_frames.csv")
