# Streaming

– Watch sensor plots / values in _real-time_ in Jupyter notebook, data is sent synchronously from Bela to the Jupyter notebook.

– Use cases: Testing sensor values over time (.e.g, how a sensor signal behaves after an interaction), sensor calibration.

– In Jupyter notebook, values can be plot dynamically (i.e., as they come). Received data is stored in a buffer, only last n points are kept (for longer windows, use logger).

– Could have callbacks, can act as (less-reliable) logger if 'saving' function is enabled

– Re fill output buffer: could also be done by writing a file in the host and reading it from jupyter notebook as suggested by Giulio.

```mermaid

flowchart TD

	classDef c_st fill:#F20505,color:white,stroke-width:0
	classDef c_io fill:#0DF205,color:white,stroke-width:0
	classDef c_p fill:yellow,stroke-width:0
	classDef c_con fill:#0511F2,color:white,stroke-width:0
	classDef c_bela fill:magenta,stroke-width:0
	style bela fill:pink,stroke-width:0
	style host fill:lightblue,stroke-width:0

	subgraph host
		direction TB
		st(["Run Jupyter Notebook server,
		open Notebook"]):::c_st
		c_all_good{"Is connection
		with Bela
		successful?"}:::c_con
		c_already_run{"Is Bela programme
		already running?"}:::c_con
		p_send_inst["Send instructions
		to run in Bela"]:::c_p

		c_is_stopped{"Stop
		Bela program?"}:::c_con

		subgraph bela
			c_comp_needed{"Is compilation
			needed?"}:::c_con
			p_compile["Compile"]:::c_p
			p_run["Run"]:::c_p

            subgraph render
                n1["in _setup()_:
                attach vars to
                streaming channel
                in _render()_
                log var to
                streaming channel in
                each render loop"]
                io_fill_obuff[/"fill streaming
                (output)
                buffer**"/]:::c_io
                c_buff_filled{"Is output
                buffer filled?"}:::c_con
            end
			c_int{"Is Bela program
			interrupted?"}:::c_con
		end

        io_receive[/"Receive data"/]:::c_io

        io_fill_ibuff[/"fill streaming
            (input) circular buffer
            fixed size, autocleans"/]:::c_io
        io_save_log[/"Log data into file in host
        (account for dropouts)"/]:::c_io
        c_saving{"Is saving
        enabled?"}:::c_con
        p_plot["Plot dynamically with bokeh
        allow freezing"]:::c_p


		st-->c_all_good
		c_all_good--yes-->c_already_run
		c_already_run--no-->p_send_inst
		c_already_run--yes-->render
		p_send_inst-->c_is_stopped

		p_send_inst-->c_comp_needed
		c_comp_needed--yes-->p_compile
		c_comp_needed--no-->p_run
		p_compile-->p_run
        p_run-->render
		render-->c_int
		%% c_comp--no-->e


        io_fill_obuff-->c_buff_filled
        c_buff_filled--yes-->io_receive
        io_receive-->c_saving
        c_saving--no-->io_fill_ibuff
        c_saving--yes-->io_save_log
        io_save_log-->io_fill_ibuff
        io_fill_ibuff-->p_plot

		c_is_stopped--yes-->c_int
		e("end"):::c_st

		c_int--yes-->e

	end
```
