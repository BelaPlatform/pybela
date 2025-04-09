from pybela import Streamer
import numpy as np


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
    streamer.send_buffer(buffer_id, buffer_type,
                         buffer_length, data_list)

if __name__ == "__main__":
    streamer = Streamer()
    streamer.connect()
    vars = ['diffFramesElapsed']
    diffs = []

    streamer.start_streaming(
        vars, on_buffer_callback=callback, callback_args=(streamer))

    # watcher is ticking inside binaryDataCallback so we need to send data to get it started
    buffer_id, buffer_type, _zeros = 0, 'i', np.zeros(buffer_length, dtype=int)
    streamer.send_buffer(buffer_id, buffer_type,
                         buffer_length, _zeros)  # send zeros buffer to get it started
    streamer.wait(2)
    streamer.stop_streaming()

    avg_roundtrip = np.round(np.average(
        diffs[1:])*1000/streamer.sample_rate, 2)  # discard first value
    print("average roundtrip ", avg_roundtrip,
          "ms ; num of buffers received: ", len(diffs))
