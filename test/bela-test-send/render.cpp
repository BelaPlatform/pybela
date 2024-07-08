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

struct CallbackBuffer {
    uint32_t guiBufferId;
    std::vector<float> bufferData;
    uint64_t count;
};
CallbackBuffer callbackBuffers[2];

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
        callbackBuffers[_id].bufferData = receivedBuffer.bufferData;
        callbackBuffers[_id].count++;
        for (size_t i = 0; i < callbackBuffers[_id].bufferData.size(); ++i) {
            *myVars[_id] = callbackBuffers[_id].bufferData[i];
        }
    }

    return true;
}

bool setup(BelaContext* context, void* userData) {

    Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
    Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher

    for (int i = 0; i < 2; ++i) {
        callbackBuffers[i].guiBufferId = Bela_getDefaultWatcherManager()->getGui().setBuffer('f', 1024);
        callbackBuffers[i].count = 0;
    }

    printf("dataBufferId_1: %d, dataBufferId_2: %d \n", callbackBuffers[0].guiBufferId, callbackBuffers[1].guiBufferId);

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
