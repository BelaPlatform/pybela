// make -C /root/Bela PROJECT=bela2python2bela-benchmark CPPFLAGS="-DNUM_AUX_VARIABLES=1" run
#include "config.h" // defines VERBOSE, NUM_AUX_VARIABLES, NUM_OSCS
#include <Bela.h>
#include <Watcher.h>
#include <cmath>
#include <vector>
#include <libraries/math_neon/math_neon.h>

std::vector<Watcher<int>*> auxWatcherVars;

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

// osc bank variables
float gPhaseIncrement;
float gFrequencies[NUM_OSCS];
float gPhases[NUM_OSCS];
float gFrequenciesLFO[NUM_OSCS];
float gPhasesLFO[NUM_OSCS];
float gScale;

bool binaryDataCallback(const std::string& addr, const WSServerDetails* id, const unsigned char* data, size_t size, void* arg) {

    uint _framesElapsed = gFramesElapsed; // copy the value of frameselapsed so that it does not vary inside the function

    receivedBuffersCount++;

    // parse received buffer
    std::memcpy(&receivedBuffer, data, receivedBufferHeaderSize);
    std::memcpy(receivedBuffer.bufferData.data(), data + receivedBufferHeaderSize, receivedBuffer.bufferLen * sizeof(int)); // data is a pointer to the beginning of the data

    int _diffFramesElapsed;
    if (receivedBuffer.bufferData[0] == 0) {
        _diffFramesElapsed = 0;
    } else {
        _diffFramesElapsed = _framesElapsed - receivedBuffer.bufferData[0];
    }

    // assign the watched variable and tick the watcher 1024 times to fill the buffer that is sent to python
    uint32_t _id = receivedBuffer.bufferId;
    for (size_t i = 0; i < receivedBuffer.bufferLen; ++i) {
        Bela_getDefaultWatcherManager()->tick(_framesElapsed); // tick needs to happen before assignment
        *auxWatcherVars[_id] = _diffFramesElapsed;
    }

    if (VERBOSE) {
        printf("\ntotal received count:  %llu, total data size: %zu, bufferId: %d, bufferType: %s, bufferLen: %d\n", receivedBuffersCount, size, receivedBuffer.bufferId, receivedBuffer.bufferType,
               receivedBuffer.bufferLen);

        printf("diff frames elapsed: %zu, _framesElapsed: %d, receivedFramesElapsed: %zu \n", auxWatcherVars[_id]->get(), _framesElapsed, receivedBuffer.bufferData[0]);
    }

    return true;
}

bool setup(BelaContext* context, void* userData) {

    printf("NUM_AUX_VARIABLES: %zu\n", NUM_AUX_VARIABLES);
    printf("NUM_OSCS: %zu\n", NUM_OSCS);

    // auxWatcherVars needs to be defined before configuring WatcherManager
    auxWatcherVars.resize(NUM_AUX_VARIABLES);
    for (unsigned int i = 0; i < NUM_AUX_VARIABLES; ++i) {
        auxWatcherVars[i] = new Watcher<int>("auxWatcherVar" + std::to_string(i));
    }

    // set up Watcher Manager
    Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
    Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher

    // set up Data Receiver
    for (unsigned int i = 0; i < NUM_AUX_VARIABLES; ++i) {
        Bela_getDefaultWatcherManager()->getGui().setBuffer('i', receivedBufferLen);
    }
    Bela_getDefaultWatcherManager()->getGui().setBinaryDataCallback(binaryDataCallback);

    receivedBuffer.bufferLen = receivedBufferLen;
    receivedBufferHeaderSize = sizeof(receivedBuffer.bufferId) + sizeof(receivedBuffer.bufferType) + sizeof(receivedBuffer.bufferLen) + sizeof(receivedBuffer.empty);
    receivedBuffer.bufferData.resize(receivedBufferLen);

    receivedBuffersCount = 0;

    // oscillator bank (to increase CPU usage)

    if (NUM_OSCS > 0) {
        gPhaseIncrement = 2.0 * M_PI * 1.0 / context->audioSampleRate;
        gScale = 1 / (float)NUM_OSCS * 0.5;

        srand(time(NULL));

        for (int k = 0; k < NUM_OSCS; ++k) {
            // Fill array gFrequencies[k] with random freq between 300 - 2700Hz
            gFrequencies[k] = rand() / (float)RAND_MAX * 2400 + 300;
            // Fill array gFrequenciesLFO[k] with random freq between 0.001 - 0.051Hz
            gFrequenciesLFO[k] = rand() / (float)RAND_MAX * 0.05 + 0.001;
            gPhasesLFO[k] = 0;
        }
    }
    return true;
}

void render(BelaContext* context, void* userData) {

    for (unsigned int n = 0; n < context->audioFrames; n++) {
        gFramesElapsed = context->audioFramesElapsed + n;

        if (NUM_OSCS > 0) {
            float out[2] = {0};

            for (int k = 0; k < NUM_OSCS; ++k) {

                // Calculate the LFO amplitude
                float LFO = sinf_neon(gPhasesLFO[k]);
                gPhasesLFO[k] += gFrequenciesLFO[k] * gPhaseIncrement;
                if (gPhasesLFO[k] > M_PI)
                    gPhasesLFO[k] -= 2.0f * (float)M_PI;

                // Calculate oscillator sinewaves and output them amplitude modulated
                // by LFO sinewave squared.
                // Outputs from the oscillators are summed in out[],
                // with even numbered oscillators going to the left channel out[0]
                // and odd numbered oscillators going to the right channel out[1]
                out[k & 1] += sinf_neon(gPhases[k]) * gScale * (LFO * LFO);
                gPhases[k] += gFrequencies[k] * gPhaseIncrement;
                if (gPhases[k] > M_PI)
                    gPhases[k] -= 2.0f * (float)M_PI;
            }
            audioWrite(context, n, 0, out[0]);
            audioWrite(context, n, 1, out[1]);
        }
    }
}

void cleanup(BelaContext* context, void* userData) {
}
