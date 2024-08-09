#include <Bela.h>
#include <Watcher.h>
#include <cmath>
#include <vector>
#include <RtThread.h>

#define NUM_OUTPUTS 2
#define MAX_EXPECTED_BUFFER_SIZE 1024

Watcher<float> pot1("pot1");
Watcher<float> pot2("pot2");

uint gPot1Ch = 0;
uint gPot2Ch = 1;

std::vector<std::vector<float>> circularBuffers(NUM_OUTPUTS);

size_t circularBufferSize = 30 * 1024;
size_t prefillSize = 2.5 * 1024;
uint32_t circularBufferWriteIndex[NUM_OUTPUTS] = {0};
uint32_t circularBufferReadIndex[NUM_OUTPUTS] = {0};

struct ReceivedBuffer {
    uint32_t bufferId;
    char bufferType[4];
    uint32_t bufferLen;
    uint32_t empty;
    std::vector<float> bufferData;
};
ReceivedBuffer receivedBuffer;
uint receivedBufferHeaderSize;
uint64_t totalReceivedCount; // total number of received buffers

unsigned int gAudioFramesPerAnalogFrame;
float gInvAudioFramesPerAnalogFrame;
float gInverseSampleRate;
float gPhase1;
float gPhase2;
float gFrequency1 = 440.0f;
float gFrequency2 = 880.0f;

// this callback is called every time a buffer is received from python. it parses the received data into the ReceivedBuffer struct, and then writes the data to the circular buffer which is read in the
// render function
bool binaryDataCallback(const std::string& addr, const WSServerDetails* id, const unsigned char* data, size_t size, void* arg) {

    if (totalReceivedCount == 0) {
        RtThread::setThisThreadPriority(1);
    }

    totalReceivedCount++;

    // parse buffer header
    std::memcpy(&receivedBuffer, data, receivedBufferHeaderSize);
    receivedBuffer.bufferData.resize(receivedBuffer.bufferLen);
    // parse buffer data
    std::memcpy(receivedBuffer.bufferData.data(), data + receivedBufferHeaderSize, receivedBuffer.bufferLen * sizeof(float));

    // write the data onto the circular buffer
    int _id = receivedBuffer.bufferId;
    if (_id >= 0 && _id < NUM_OUTPUTS) {
        for (size_t i = 0; i < receivedBuffer.bufferLen; ++i) {
            circularBuffers[_id][circularBufferWriteIndex[_id]] = receivedBuffer.bufferData[i];
            circularBufferWriteIndex[_id] = (circularBufferWriteIndex[_id] + 1) % circularBufferSize;
        }
    }

    return true;
}

bool setup(BelaContext* context, void* userData) {

    Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
    Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher

    gAudioFramesPerAnalogFrame = context->audioFrames / context->analogFrames;
    gInvAudioFramesPerAnalogFrame = 1.0 / gAudioFramesPerAnalogFrame;
    gInverseSampleRate = 1.0 / context->audioSampleRate;

    // initialize the Gui buffers and circular buffers
    for (int i = 0; i < NUM_OUTPUTS; ++i) {
        Bela_getDefaultWatcherManager()->getGui().setBuffer('f', MAX_EXPECTED_BUFFER_SIZE);
        circularBuffers[i].resize(circularBufferSize, 0.0f);
        // the write index is given some "advantage" (prefillSize) so that the read pointer does not catch up the write pointer
        circularBufferWriteIndex[i] = prefillSize % circularBufferSize;
    }

    Bela_getDefaultWatcherManager()->getGui().setBinaryDataCallback(binaryDataCallback);

    // vars and preparation for parsing the received buffer
    receivedBufferHeaderSize = sizeof(receivedBuffer.bufferId) + sizeof(receivedBuffer.bufferType) + sizeof(receivedBuffer.bufferLen) + sizeof(receivedBuffer.empty);
    totalReceivedCount = 0;
    receivedBuffer.bufferData.reserve(MAX_EXPECTED_BUFFER_SIZE);

    return true;
}

void render(BelaContext* context, void* userData) {
    for (unsigned int n = 0; n < context->audioFrames; n++) {
        uint64_t frames = context->audioFramesElapsed + n;

        if (gAudioFramesPerAnalogFrame && !(n % gAudioFramesPerAnalogFrame)) {
            Bela_getDefaultWatcherManager()->tick(frames * gInvAudioFramesPerAnalogFrame); // watcher timestamps

            // read sensor values and put them in the watcher
            pot1 = analogRead(context, n / gAudioFramesPerAnalogFrame, gPot1Ch);
            pot2 = analogRead(context, n / gAudioFramesPerAnalogFrame, gPot2Ch);

            // read the values sent from python (they're in the circular buffer)
            for (unsigned int i = 0; i < NUM_OUTPUTS; i++) {

                if (totalReceivedCount > 0 && (circularBufferReadIndex[i] + 1) % circularBufferSize != circularBufferWriteIndex[i]) {
                    circularBufferReadIndex[i] = (circularBufferReadIndex[i] + 1) % circularBufferSize;
                } else if (totalReceivedCount > 0) {
                    rt_printf("The read pointer has caught the write pointer up in buffer %d – try increasing prefillSize\n", i);
                }
            }
        }
        float amp1 = circularBuffers[0][circularBufferReadIndex[0]];
        float amp2 = circularBuffers[1][circularBufferReadIndex[1]];

        float out = amp1 * sinf(gPhase1) + amp2 * sinf(gPhase2);

        for (unsigned int channel = 0; channel < context->audioOutChannels; channel++) {
            audioWrite(context, n, channel, out);
        }

        gPhase1 += 2.0f * (float)M_PI * gFrequency1 * gInverseSampleRate;
        if (gPhase1 > M_PI)
            gPhase1 -= 2.0f * (float)M_PI;
        gPhase2 += 2.0f * (float)M_PI * gFrequency2 * gInverseSampleRate;
        if (gPhase2 > M_PI)
            gPhase2 -= 2.0f * (float)M_PI;
    }
}

void cleanup(BelaContext* context, void* userData) {
}