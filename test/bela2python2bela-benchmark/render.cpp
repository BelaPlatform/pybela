#include <Bela.h>
#include <Watcher.h>
#include <cmath>

Watcher<int> diffFramesElapsed("diffFramesElapsed");

unsigned int counter = 0;
unsigned int gFramesElapsed = 0;
struct ReceivedBuffer {
    uint32_t bufferId;
    char bufferType[4];
    uint32_t bufferLen;
    uint32_t empty;
    std::vector<int> bufferData;
};
ReceivedBuffer receivedBuffer;
uint receivedBufferHeaderSize;
uint64_t totalReceivedCount;


bool binaryDataCallback(const std::string& addr, const WSServerDetails* id, const unsigned char* data, size_t size, void* arg) {

    totalReceivedCount++;

    std::memcpy(&receivedBuffer, data, receivedBufferHeaderSize);
    receivedBuffer.bufferData.resize(receivedBuffer.bufferLen);
    std::memcpy(receivedBuffer.bufferData.data(), data + receivedBufferHeaderSize, receivedBuffer.bufferLen * sizeof(float)); // data is a pointer to the beginning of the data

    printf("\ntotal received count:  %llu, total data size: %zu, bufferId: %d, bufferType: %s, bufferLen: %d \n", totalReceivedCount, size, receivedBuffer.bufferId, receivedBuffer.bufferType,
           receivedBuffer.bufferLen);

    for (size_t i = 0; i < receivedBuffer.bufferLen; ++i) {
            diffFramesElapsed = gFramesElapsed-receivedBuffer.bufferData[0];
            Bela_getDefaultWatcherManager()->tick(gFramesElapsed);
        }

    return true;
}

bool setup(BelaContext* context, void* userData) {

    Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
    Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher

    Bela_getDefaultWatcherManager()->getGui().setBuffer('i',1024);


    Bela_getDefaultWatcherManager()->getGui().setBinaryDataCallback(binaryDataCallback);

    receivedBufferHeaderSize = sizeof(receivedBuffer.bufferId) + sizeof(receivedBuffer.bufferType) + sizeof(receivedBuffer.bufferLen) + sizeof(receivedBuffer.empty);
    totalReceivedCount = 0;
    Bela_getDefaultWatcherManager()->tick(totalReceivedCount); // init the watcher

    return true;
}

void render(BelaContext* context, void* userData) {

        for (unsigned int n = 0; n < context->audioFrames; n++) {
            gFramesElapsed = context->audioFramesElapsed + n;
        }
    
}

void cleanup(BelaContext* context, void* userData) {
}
