#include <Bela.h>
#include <Watcher.h>
#include <cmath>

Watcher<float> myvar1("myvar1");
Watcher<float> myvar2("myvar2");

std::vector<Watcher<float>*> myVars = {&myvar1, &myvar2};

struct ReceivedBuffer {
    uint32_t bufferId;
    char bufferType[4];
    uint32_t bufferLen;
    uint32_t empty;
    std::vector<float> bufferData;
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

    Bela_getDefaultWatcherManager()->tick(totalReceivedCount);
    int _id = receivedBuffer.bufferId;
    if (_id >= 0 && _id < myVars.size()) {

        for (size_t i = 0; i < receivedBuffer.bufferData.size(); ++i) {
            *myVars[_id] = receivedBuffer.bufferData[i];
        }
    }

    return true;
}

bool setup(BelaContext* context, void* userData) {

    Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
    Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher

    for (int i = 0; i < 2; ++i) {
        Bela_getDefaultWatcherManager()->getGui().setBuffer('f', 1024);
    }

    Bela_getDefaultWatcherManager()->getGui().setBinaryDataCallback(binaryDataCallback);

    receivedBufferHeaderSize = sizeof(receivedBuffer.bufferId) + sizeof(receivedBuffer.bufferType) + sizeof(receivedBuffer.bufferLen) + sizeof(receivedBuffer.empty);
    totalReceivedCount = 0;
    Bela_getDefaultWatcherManager()->tick(totalReceivedCount); // init the watcher

    return true;
}

void render(BelaContext* context, void* userData) {
    //	DataBuffer& receivedBuffer =
    // Bela_getDefaultWatcherManager()->getGui().getDataBuffer(dataBufferId);
    //	float* data = receivedBuffer.getAsFloat();
}

void cleanup(BelaContext* context, void* userData) {
}
