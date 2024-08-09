#include <Watcher.h>
Watcher<double> myvar("myvar");
Watcher<unsigned int> myvar2("myvar2");
Watcher<unsigned int> myvar3("myvar3", WatcherManager::kTimestampSample);
Watcher<double> myvar4("myvar4", WatcherManager::kTimestampSample);
Watcher<double> myvar5("myvar5");



#include <Bela.h>
#include <cmath>

bool setup(BelaContext *context, void *userData)
{
	Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
	Bela_getDefaultWatcherManager()->setup(context->audioSampleRate); // set sample rate in watcher

	return true;
}

void render(BelaContext *context, void *userData)
{

	static size_t count = 0;
	if(1) // if(count++ >= context->audioSampleRate * 0.6 / context->audioFrames)
	{
		//rt_printf("%.5f %.5f\n\r", float(myvar), float(myvar2));
		static int pastC = -1;
		static int pastAC = -1;
		int c = Bela_getDefaultWatcherManager()->getGui().numConnections();
		int ac = Bela_getDefaultWatcherManager()->getGui().numActiveConnections();
		if(c != pastC || ac != pastAC)
			rt_printf("connected %d %d\n", c, ac);
		pastC = c;
		pastAC = ac;
		count = 0;
	}

	for(unsigned int n = 0; n < context->audioFrames; n++) {
		uint64_t frames = context->audioFramesElapsed + n;
		Bela_getDefaultWatcherManager()->tick(frames);

		myvar = frames;
		myvar2 = frames; // log a dense variable densely: good
		myvar5 = frames;
		
		if(frames % 12 == 0){ // log a sparse variable sparsely: good
			myvar3 = frames;
			myvar4 = frames;
		}

	}
}

void cleanup(BelaContext *context, void *userData)
{
}
