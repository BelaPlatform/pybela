# Monitoring
– Observe variables at specific times. 

– Data is monitored in cpp, and data blocks are sent asynchronously when requested by the Jupyter notebook. Callbacks in Bela set flags when e.g., values change. Flags can be read synchronously in Jupyter notebook. 

– Use cases: Testing sensors at specific times (e.g., sensor rest value, when does a sensor value change), debugging

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

		io_req[/"Request value / block
		of monitored variable"/]:::c_io

		c_is_stopped{"Stop
		Bela program?"}:::c_con

		subgraph bela
			c_comp_needed{"Is compilation
			needed?"}:::c_con
%%			p_run_ren["enter render() loop"]:::c_p
%%			p_end_ren["end of render()"]:::c_p

			p_compile["Compile"]:::c_p
%%			c_comp{"Compilation
%%			successful"}:::c_con
			p_run["Run"]:::c_p
			subgraph render
				n1["in _setup()_:
				attach vars to 
				monitoring channel
				in _render()_
				log var to 
				monitoring channel in 
				each render loop"]
				io_put[/"Log data in
				monitoring channel"/]:::c_io
				c_req{"Is there a 
				monitoring 
				request?"}:::c_con
				io_send[/"Send data to host"/]:::c_io
			end
			c_int{"Is Bela program
			interrupted?"}:::c_con
		end

		io_receive[/"Receive data
		(block or var)"/]:::c_io
		p_proc[Plot/store/...]:::c_p
       


		st-->c_all_good
		c_all_good--yes-->c_already_run
		c_already_run--no-->p_send_inst
		p_send_inst-->io_req
		io_req-->c_req

		c_already_run--yes-->render
		p_send_inst-->c_is_stopped

		p_send_inst-->c_comp_needed
		c_comp_needed--yes-->p_compile
		c_comp_needed--no-->p_run
		p_compile-->p_run
        p_run-->render
		render-->c_int
		io_put-->c_req
		c_req--yes-->io_send
		io_send-->io_receive
		io_receive-->p_proc
		p_proc-->e


		c_is_stopped--yes-->c_int
		e("end"):::c_st

		c_int--yes-->e

	end
```
