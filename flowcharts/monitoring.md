# Monitoring
– Observe variables at specific times. 

– Data is monitored in cpp, and data blocks are sent asynchronously when requested by the Jupyter notebook. Callbacks in Bela set flags when e.g., values change. Flags can be read synchronously in Jupyter notebook. 

– Use cases: Testing sensors at specific times (e.g., sensor rest value, when does a sensor value change), debugging

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
	style monitorclass fill:khaki,stroke-width:0



	subgraph host
		direction TB
		st(["Run Jupyter Notebook server,
		open Notebook"]):::c_st
		c_all_good{"Is connection
		with Bela
		successful?"}:::c_con

		io_start[/"Init monitoring session 
		start_monitor(project_name)"/]:::c_io
	
		io_req[/"Request value / block
		of monitored variable"/]:::c_io

		subgraph bela

			subgraph setup
				p_monitor_setup["Setup monitoring channel \n monitorCh1 = monitor.setupChannel(idx = 1, type = float"]:::c_p
			end

			subgraph render
				io_put[/"Put data in
				monitoring channel \n
				monitorCh1.monitor(variable)
				"/]:::c_io

				subgraph monitorclass
					c_req{"Is there a 
					monitoring 
					request?"}:::c_con
					io_send[/"[Handle monitor req]
					and send data to host"/]:::c_io

				end
			end

		end

		
		msg_start[/"msg: ''Monitoring started''"/]:::c_msg
		msg_e[/"msg: ''Monitoring finished''"/]:::c_msg

		io_receive[/"Receive data
		(block or var)"/]:::c_io
		p_proc[Plot/store/...]:::c_p
       

	
		st-->c_all_good
		c_all_good--yes-->setup
		
		setup -->render

		io_start-->io_put
		io_put-->msg_start
		io_put-->c_req
		c_req--yes-->io_send

		io_send-->msg_e

		io_send-->io_receive
		io_receive-->p_proc

		io_req-->c_req


		e("end"):::c_st


	end
```
