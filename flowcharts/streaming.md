# Streaming

– Watch sensor plots / values in _real-time_ in Jupyter notebook, data is sent synchronously from Bela to the Jupyter notebook.

– Use cases: Testing sensor values over time (.e.g, how a sensor signal behaves after an interaction), sensor calibration.

– In Jupyter notebook, values can be plot dynamically (i.e., as they come). Received data is stored in a buffer, only last n points are kept (for longer windows, use logger).

– Could have callbacks, can act as (less-reliable) logger if 'saving' function is enabled

– Re fill output buffer: could also be done by writing a file in the host and reading it from jupyter notebook as suggested by Giulio.

```mermaid

flowchart TD


	classDef c_st fill:indianred,stroke-width:0
	classDef c_io fill:lawngreen,stroke-width:0
	classDef c_p fill:sandybrown,stroke-width:0
	classDef c_msg fill:lightgreen,stroke-width:0
	classDef c_con fill:cornflowerblue,stroke-width:0
	classDef c_bela fill:magenta,stroke-width:0

	style host fill:beige,stroke-width:0
	style bela fill:paleturquoise,stroke-width:0
	style setup fill:peachpuff,stroke-width:0
	style render fill:thistle,stroke-width:0

	subgraph host
		direction TB
		st(["Run Jupyter Notebook server,
		open Notebook"]):::c_st
		c_all_good{"Is connection
		with Bela
		successful?"}:::c_con


		io_start[/"Init streaming session 
		start_streaming(project_name, n_frames)"/]:::c_io

		subgraph bela

			
			subgraph setup
				p_stream_setup["Setup streaming channel \n streamCh1 = streamer.setupChannel(idx = 1, type = float"]:::c_p
			end


            subgraph render
     
                io_fill_obuff[/"Put variable in streaming channel
				streamCh1.stream(variable)"/]:::c_io
				c_mode{"Stream n_frames 
				or until stopped?"}:::c_con
                c_buff_filled{"Have n_frames been 
				streamed already?"}:::c_con
            end

			c_stop{"Bela stopped?"}:::c_con

		end

        io_receive[/"Receive data"/]:::c_io

        io_fill_ibuff[/"Fill streaming
            (input) jupyter circular buffer of fixed size
            "/]:::c_io
        io_save_log[/"Log data into file in host
        (account for dropouts)"/]:::c_io
        c_saving{"Is saving
        enabled?"}:::c_con
        p_plot["Plot dynamically with bokeh
        allow freezing"]:::c_p

				
		msg_start[/"msg: ''Streaming started''"/]:::c_msg
		msg_e[/"msg: ''Streaming finished''"/]:::c_msg

		st-->c_all_good
		c_all_good--yes-->io_start
		io_start-->io_fill_obuff
		io_fill_obuff-->msg_start
		io_fill_obuff-->c_mode
		c_mode--inf-->c_stop
		c_stop--no-->io_receive
		c_stop--yes-->msg_e
		c_mode--n_frames-->c_buff_filled
		c_buff_filled--no-->io_receive
		c_buff_filled--yes-->msg_e


		setup-->render

        io_receive-->c_saving
        c_saving--no-->io_fill_ibuff
        c_saving--yes-->io_save_log
        io_save_log-->io_fill_ibuff
        io_fill_ibuff-->p_plot


		e("end"):::c_st

	end
```
