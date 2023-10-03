#include <Watcher.h>
Watcher<float> pot1("pot1");
Watcher<float> pot2("pot2");

#include <Bela.h>
#include <cmath>

float gInverseSampleRate;
int gAudioFramesPerAnalogFrame = 0;

// Analog inputs for each potentiometer 
uint gPot1Ch = 0;
uint gPot2Ch = 1;

bool setup(BelaContext *context, void *userData)
{
	gui.setup(context->projectName);
	Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher
	gAudioFramesPerAnalogFrame = context->audioFrames / context->analogFrames;
	gInverseSampleRate = 1.0 / context->audioSampleRate;
	return true;
}

void render(BelaContext *context, void *userData)
{
	for(unsigned int n = 0; n < context->audioFrames; n++) {
		if(gAudioFramesPerAnalogFrame && !(n % gAudioFramesPerAnalogFrame)) {
			
			uint64_t frames = context->audioFramesElapsed/gAudioFramesPerAnalogFrame + n/gAudioFramesPerAnalogFrame;
			Bela_getDefaultWatcherManager()->tick(frames); // watcher timestamps
			
			pot1 = analogRead(context,  n/gAudioFramesPerAnalogFrame, gPot1Ch);
			pot2 = analogRead(context,  n/gAudioFramesPerAnalogFrame, gPot2Ch);
			
		}
	}
}

void cleanup(BelaContext *context, void *userData)
{
}
