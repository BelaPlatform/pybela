from pybela import Streamer
import numpy as np

diffs = []

async def callback(buffer,streamer):    
    diffs.append(buffer['buffer']['data'][0])
    
    buffer_id, buffer_type, buffer_length = 0, 'i', 1024
    data_list = np.ones(buffer_length, dtype=int)*buffer['buffer']['ref_timestamp']
    streamer.send_buffer(buffer_id, buffer_type,
                            buffer_length, data_list)
    
if __name__ == "__main__":
    streamer = Streamer()
    streamer.connect()
    vars = ['diffFramesElapsed']
    
    streamer.start_streaming(
        vars, on_buffer_callback=callback, callback_args=(streamer))
    buffer_id, buffer_type, buffer_length = 0, 'i', 1024
    data_list = np.zeros(buffer_length, dtype=int)

    streamer.send_buffer(buffer_id, buffer_type,
                            buffer_length, data_list) # send zeros buffer to get it started
    streamer.send_buffer(buffer_id, buffer_type,
                            buffer_length, data_list) # send zeros buffer to get it started

    streamer.wait(1)
    streamer.stop_streaming()
    
    avg_roundtrip = np.round(np.average(diffs[4:])/streamer.sample_rate, 3)*1000
    print("average roundtrip ", avg_roundtrip) # discard first measurements
