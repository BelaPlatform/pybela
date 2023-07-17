# Logging 
– Log sensor values in a file during an 'extended' period of time. Data is logged in a file in Bela and then transferred to the host machine. 

– Use cases: recording dataset, collecting study data

– Note: In this case, the Jupyter notebook starts the logging session ("triggers" the Bela code). Once the Bela code is interrupted, the logging file is copied from Bela to the host. If the user wants to run the logging program directly from Bela without interfacing with Jupyter notebook, the only notebook's function is to copy the log files from the Bela to the host, which is a more general API case and hence is not included in this document.

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
		io_name[/"Init logging session and
		give it a name / unique id
		start_log(project_name, log_file_name)"/]:::c_io

		io_stop[/"In python, stop logging
		logger.stop()"/]:::c_io

		subgraph bela

			subgraph setup
				p_logch_setup["Setup logger channel \n logCh1 = logger.setupChannel(idx = 1, type = int"]:::c_p
			end

			subgraph render
				io_create[/"Create log file withgiven name 
				configure_file(file_name)"/]:::c_io

				c_mode{"Stream n_frames 
				or until interrupted?"}:::c_con

				c_while{" 
				Logged frames 
				< requested frames 
				to log (n_frames) ?"}:::c_con
		
				io_log[/"log variable into log file
				logCh1.log(variable)"/]:::c_io

				p_finish["Finish logging"]:::c_p
			end
			c_stop{"Bela stopped?"}:::c_con

			
		end

		msg_start[/"msg: ''Logging started''"/]:::c_msg
		msg_e[/"msg: ''Logging finished''"/]:::c_msg


		c_copy{"Does user 
		want to copy 
		log to the 
		laptop
		?"}:::c_con
		p_copy["Copy files to laptop (scp)"]:::c_p
		p_load["Decode and load 
		in Jupyter Notebook"]:::c_p

		st-->c_all_good
		c_all_good--yes-->io_name

		io_name-->io_create
		io_create-->msg_start
		io_create-->c_mode
		c_mode--n_frames-->c_while
		c_mode--inf-->c_stop
		c_stop--yes-->p_finish
		p_finish-->msg_e
		io_stop-->p_finish

		c_while--yes-->io_log
		io_log-->c_while
		c_while--no-->p_finish
		msg_e-->c_copy

		setup-->render
	
		e("end"):::c_st
		
		c_copy--yes-->p_copy--->p_load
	end
```

