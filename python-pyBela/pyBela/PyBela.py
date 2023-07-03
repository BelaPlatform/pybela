class BelaConnection:
    # Handles connection to Bela through websockets
    
    def connect():
        # Connect to Bela websocket
        # Return: True if connection was successful, False otherwise
        
    def disconnect():
        # Disconnect from Bela websocket
        # Return: True if disconnection was successful, False otherwise
        
    def isConnected():
        # Connection status
        # Return: True if connected, False otherwise


class BelaProgram:
    # Handles running/stopping programs on Bela
    
    def isRunning():
        # Return: Program name if program is running, None otherwise
        
    def run(program_name, make_flags):
        # program_name : str -- name of the program to run
        # make_flags : str -- flags to pass to make
        # Run program and pass given flags
        
    def stop():
        # Stop program 
        

class BelaStreamingData:
    # Handles streaming data from Bela to the host
    
    def listen():
        # Check if Bela is connected and program is running, then listen to data stream
        # Use threading and allow with statement
        # Return data stream
    
    def save(path):
        # path : str -- path to save the data to
        # Save the data to a file
     
        
class BelaMonitor:
    # Handles request and reception of monitored variables in Bela
    
    def monitored():
        # Request list of monitored variables 
    
    def get(id):
        # id : int -- id of the monitored variable
        # Returns value or block of monitored variable
    
    def receive(id):
        # id : int -- id of the monitored variable
        # Returns received data from Bela
    

class BelaLogger:
    # Handles creating logging session, copying log files to host, loading log files
    # (logging session is started with BelaProgram.run())
    
    def create(id):
        # id : int -- id of the logging session
        # Create logging session
        # Return True if successful, False otherwise
    
    def copy():
        # Copy log files from the Bela to the host 
        # Return True if successful, False otherwise
        
    def load(filepath):
        # filepath : str -- path to log file
        # Decode and load log file
    
        
    
        
    