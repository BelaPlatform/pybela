# Logging 
– Log sensor values in a file during an 'extended' period of time. Data is logged in a file in Bela and then transferred to the host machine. 

– Use cases: recording dataset, collecting study data

– Note: In this case, the Jupyter notebook starts the logging session ("triggers" the Bela code). Once the Bela code is interrupted, the logging file is copied from Bela to the host. If the user wants to run the logging program directly from Bela without interfacing with Jupyter notebook, the only notebook's function is to copy the log files from the Bela to the host, which is a more general API case and hence is not included in this document.

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
		io_name[/"Give logging session 
		a name / unique id"/]:::c_io
		p_send_inst["Send instructions
		to run in Bela"]:::c_p
		c_is_stopped{"Stop 
		Bela program?"}:::c_con
		
		subgraph bela
			c_comp_needed{"Is compilation 
			needed?"}:::c_con
			
			p_compile["Compile"]:::c_p
			p_run["Run passing the
			log file name"]:::c_p
			
			io_create[/"Create log file with
			given name"/]:::c_io
			subgraph render
				n1["in _setup()_: 
				attach vars to logging channel
				in _render()_
				log var to file if condition is satisfied"]
				io_log[/"log variable 
				into log file
				(if given condition)"/]:::c_io
			end

			c_int{"Is Bela program
			interrupted?"}:::c_con
			
		end

		c_copy{"Does user 
		want to copy 
		log to the 
		laptop
		?"}:::c_con
		p_copy["Copy files to laptop"]:::c_p
		p_load["Decode and load 
		in Jupyter Notebook"]:::c_p

		st-->c_all_good
		c_all_good--yes-->io_name
		io_name-->p_send_inst
		p_send_inst-->c_is_stopped

		p_send_inst-->c_comp_needed
		c_comp_needed--yes-->p_compile
		c_comp_needed--no-->p_run
		p_compile-->p_run


		io_create-->render

	
		p_run-->io_create
		render-->c_int
		c_is_stopped--yes-->c_int
		e("end"):::c_st
		

		
		c_int--yes-->c_copy
		c_copy--no-->e
		c_copy--yes-->p_copy--->p_load--->e
	end
```

