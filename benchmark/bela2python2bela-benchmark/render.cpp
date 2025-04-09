#include <Bela.h>
#include <Watcher.h>
#include <cmath>

Watcher<int> auxWatcherVar("auxWatcherVar");

#define VERBOSE 1 

struct ReceivedBuffer {
    uint32_t bufferId;
    char bufferType[4];
    uint32_t bufferLen;
    uint32_t empty;
    std::vector<int> bufferData;
};
ReceivedBuffer receivedBuffer;
uint receivedBufferHeaderSize;
uint receivedBufferLen = 1024; // size of the buffer to be received from python
uint64_t receivedBuffersCount;

uint gFramesElapsed = 0;

bool binaryDataCallback(const std::string& addr, const WSServerDetails* id, const unsigned char* data, size_t size, void* arg) {

    uint _framesElapsed = gFramesElapsed; // copy the value of frameselapsed so that it does not vary inside the function

    receivedBuffersCount++;
    
    // parse received buffer
    std::memcpy(&receivedBuffer, data, receivedBufferHeaderSize);
    std::memcpy(receivedBuffer.bufferData.data(), data + receivedBufferHeaderSize, receivedBuffer.bufferLen * sizeof(int)); // data is a pointer to the beginning of the data
    
    uint _diffFramesElapsed;
    if (receivedBuffer.bufferData[0]==0){
        _diffFramesElapsed = 0;
    } else{
        _diffFramesElapsed = _framesElapsed - receivedBuffer.bufferData[0];
    }

    // assign the watched variable and tick the watcher 1024 times to fill the buffer that is sent to python
    for (size_t i = 0; i < receivedBuffer.bufferLen; ++i) {
        Bela_getDefaultWatcherManager()->tick(_framesElapsed); // tick needs to happen before assignment
        auxWatcherVar = _diffFramesElapsed;
    }

    if (VERBOSE){
        printf("\ntotal received count:  %llu, total data size: %zu, bufferId: %d, bufferType: %s, bufferLen: %d\n", receivedBuffersCount, size, receivedBuffer.bufferId, receivedBuffer.bufferType,receivedBuffer.bufferLen);

        printf("\n diff frames elapsed: %d, _framesElapsed: %d, receivedFramesElapsed: %zu \n", auxWatcherVar.get(),_framesElapsed, receivedBuffer.bufferData[0]);
    }

    return true;
}

bool setup(BelaContext* context, void* userData) {

    // set up Watcher Manager
    Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
    Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher

    // set up Data Receiver
    Bela_getDefaultWatcherManager()->getGui().setBuffer('i',receivedBufferLen);
    Bela_getDefaultWatcherManager()->getGui().setBinaryDataCallback(binaryDataCallback);

    receivedBuffer.bufferLen = receivedBufferLen;    
    receivedBufferHeaderSize = sizeof(receivedBuffer.bufferId) + sizeof(receivedBuffer.bufferType) + sizeof(receivedBuffer.bufferLen) + sizeof(receivedBuffer.empty);
    receivedBuffer.bufferData.resize(receivedBufferLen);

    receivedBuffersCount = 0;

    return true;
}

void render(BelaContext* context, void* userData) {

        for (unsigned int n = 0; n < context->audioFrames; n++) {
            gFramesElapsed = context->audioFramesElapsed + n;
        }
    
}

void cleanup(BelaContext* context, void* userData) {
}
