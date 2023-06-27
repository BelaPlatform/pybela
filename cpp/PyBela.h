# include <vector>

class PyBela{
    // Runtime PyBela API prototype 

    private:
        // Logging API
        int nLogBufferChannels; // number of channels in the log buffer -- * channels act as the variable identifier
        int logBufferSize; // size of the logging buffer
        std::vector<<vector<int>> logBuffer; // logging buffer -- 2d: channel x buffer
        void writeLogBuffer(); // once logBuffer is full, writes the log buffer to the log file
        bool createLogFile(str logFileName); // creates a log file with the given name

        // Streaming API
        int nStreamBufferChannels; // number of channels in the stream buffer -- * channels act as the variable identifier
        int streamBufferSize; // size of the streaming buffer
        std::vector<<vector<int>> streamBuffer; // streaming buffer -- 2d: channel x buffer 
        void sendStreamingBuffer(); // once the streaming buffer is filled, it is sent to the host via websockets

        // Monitoring API
        int nMonitorBufferChannels; // number of channels in the monitor buffer -- * channels act as the variable identifier
        int monitorBufferSize; // size of the monitoring buffer
        std::vector<<nMonitorBufferChannels<int>> monitorBuffer; // monitoring buffer (sent on request)
        void listenForMonitorRequest(); // listens for a monitor request from the host
        void sendMonitorBuffer(); // sends the monitoring buffer to the host when requested 


    public:
        PyBela();
        ~PyBela();

        // Communication API -- there's already the WSServer class, this might be unnecessary
        bool initCommunication(); // sets up websockets, returns true if successful
        bool stopCommunication(); // stops websockets, returns true if successful
        str communicationStatus(); // returns the status of the websocket connection
        void send(str message); // sends a message to the host -- useful for testing
        str receive(); // receives a message from the host -- useful for testing

        // Logging API
        bool initLog(str fileName); // to be called in setup(), creates log file and sets up buffer 
        void log(std::vector<std::vector<int>> logBuffer, str encoding); // either value, array or string? -- should be in binary
        
        // Streaming API
        bool initStream(); // to be called in setup(), frequency, channels, buffer size
        void stream(std::vector<std::vector<int>> streamBuffer,  int logChannel); 
     
        // Monitoring API
        bool initMonitor(); // to be called in setup()
        void monitor(std::vector<std::vector<int>> monitorBuffer,  int monitorChannel); // listens for monitor request, sends value(s) when requested


}