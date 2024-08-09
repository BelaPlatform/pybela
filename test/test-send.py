import unittest
from pybela import Streamer
import struct
import numpy as np
import asyncio

streamer = Streamer()
variables = ["myvar1", "myvar2"]


async def wait():
    await asyncio.sleep(0.1)

# can't be merged with test.py because in the render.cpp the watcher needs to be 'ticked' when iterating the buffer, not at every audio frame!

# TOOD test other types (int, double, uint, char)


class test_Sender(unittest.TestCase):
    def test_send_buffer(self):
        if streamer.connect():

            streamer.start_streaming(variables)

            # Pack the data into binary format
            # >I means big-endian unsigned int, 4s means 4-byte string, pad with x for empty bytes

            for id in [0, 1]:
                # buffers are only sent from Bela to the host once full, so it needs to be 1024 long to be sent
                buffer_id, buffer_type, buffer_length, empty = id, 'f', 1024, 0
                data_list = np.arange(1, buffer_length+1, 1)
                streamer.send_buffer(buffer_id, buffer_type,
                                     buffer_length, data_list)

            asyncio.run(wait())  # wait for the buffer to be sent

            for var in variables:
                assert np.array_equal(
                    streamer.streaming_buffers_data[var], data_list), "Data sent and received are not the same"

            streamer.stop_streaming()


if __name__ == '__main__':
    unittest.main(verbosity=2)
    suite = unittest.TestSuite()
    suite.addTest(test_Sender('test_send_buffer'))
