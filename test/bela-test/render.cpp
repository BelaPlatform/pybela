#include <Watcher.h>
Watcher<double> myvar("myvar");
Watcher<unsigned int> myvar2("myvar2");
Watcher<unsigned int> myvar3("myvar3", WatcherManager::kTimestampSample);
Watcher<double> myvar4("myvar4", WatcherManager::kTimestampSample);


#include <Bela.h>
#include <cmath>

float gFrequency = 440.0;
float gPhase;
float gInverseSampleRate;

bool setup(BelaContext *context, void *userData)
{
	gui.setup(context->projectName);
	Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher
	gInverseSampleRate = 1.0 / context->audioSampleRate;
	gPhase = 0.0;
	return true;
}

void render(BelaContext *context, void *userData)
{

	static size_t count = 0;
	if(count++ >= context->audioSampleRate * 0.6 / context->audioFrames)
	{
		//rt_printf("%.5f %.5f\n\r", float(myvar), float(myvar2));
		static int pastC = -1;
		int c = gui.numConnections();
		if(c != pastC)
			rt_printf("connected %d\n", c);
		pastC = c;
		count = 0;
	}

	for(unsigned int n = 0; n < context->audioFrames; n++) {
		uint64_t frames = context->audioFramesElapsed + n;
		Bela_getDefaultWatcherManager()->tick(frames);

		myvar = frames;
		myvar2 = frames; // log a dense variable densely: good
		
		if(frames % 12 == 0){ // log a sparse variable sparsely: good
			myvar3 = frames;
			myvar4 = frames;
		}

		float out = 0.8 * sinf(gPhase);
		gPhase += 2.0 * M_PI * gFrequency * gInverseSampleRate;
		if(gPhase > 2.0 * M_PI)
			gPhase -= 2.0 * M_PI;

		for(unsigned int channel = 0; channel < context->audioOutChannels; channel++) {
			audioWrite(context, n, channel, out);
		}
	}
}

void cleanup(BelaContext *context, void *userData)
{
}
