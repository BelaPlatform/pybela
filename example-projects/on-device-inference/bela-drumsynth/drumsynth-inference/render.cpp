/**
 * Audio Driven Drum Synthesis
 * MAP Final Project - 2023
 * Jordie Shier
 * 
 * Snare drum synthesizer based on early drum machines that
 * can be triggered and controlled in response to audio
 * input from a microphone.
 */
 
 #define WATCHING 0 // Turn on to watch with PyBela - disables GUI.
 
#include <Bela.h>
#include <libraries/Gui/Gui.h>
#include <libraries/GuiController/GuiController.h>
#include <algorithm>
#include <cmath>

#include "SnareDrum.h"


#if WATCHING == 1

#include "Watcher.h"
#include "DrumController.h"

 // Watcher variables
Watcher<float> spectralCentroid("spectralCentroid");
Watcher<float> onsetEnergy("onsetEnergy");

#else

#include "DrumControllerInference.h"

#endif

// Browser-based GUI to adjust parameters
Gui gGui;
GuiController gGuiController;

// Synthesis & Synth Controller
SnareDrum drum;
DrumController controller(drum);

// Globals to help with GUI parameter mapping
int paramStartIndex;
int numParams;

bool setup(BelaContext *context, void *userData)
{
	// Setup processors
	drum.prepare(context->audioSampleRate);
	controller.prepare(context->audioSampleRate);
	
	// Initialize drum params
	auto& noise = drum.getNoise();
	noise.setDecay(0.25);
	noise.setColor(0.25);
	noise.setTone(0.75);
	
	auto& tonal = drum.getTonal();
	tonal.setDecay(0.25);
	tonal.setTuning(0.5);
	
#if WATCHING == 1
	// Setup the Watcher -- need to add both these lines for the watcher
	Bela_getDefaultWatcherManager()->getGui().setup(context->projectName);
	Bela_getDefaultWatcherManager()->setup(context->audioSampleRate);
#else
	// Set up the GUI
	gGui.setup(context->projectName);
	gGuiController.setup(&gGui, "Drum Control");

	// Load the drum mapping model
	AppOptions *opts = reinterpret_cast<AppOptions *>(userData);
	if (!controller.loadModel(opts)) {
		return false;
	}
#endif
	
	// Arguments: name, default value, minimum, maximum, increment
	gGuiController.addSlider("Listen", 0.0, 0.0, 1.0, 1.0);
	gGuiController.addSlider("Trigger Threshold", 16.0, 0.0, 30.0, 0);
	
	paramStartIndex = 2;
	numParams = 7;
	gGuiController.addSlider("Tonal Decay", 0.30, 0.0, 1.0, 0);
	gGuiController.addSlider("Tonal Decay Energy Mod", 0.0, -1.0, 1.0, 0);
	gGuiController.addSlider("Tonal Decay Spectral Mod", 0.0, -1.0, 1.0, 0);
	
	gGuiController.addSlider("Tonal Tuning", 0.60, 0.0, 1.0, 0);
	gGuiController.addSlider("Tonal Tuning Energy Mod", 0.0, -1.0, 1.0, 0);
	gGuiController.addSlider("Tonal Tuning Spectral Mod", 0.0, -1.0, 1.0, 0);
	
	gGuiController.addSlider("Noise Decay", 0.30, 0.0, 1.0, 0);
	gGuiController.addSlider("Noise Decay Energy Mod", 0.0, -1.0, 1.0, 0);
	gGuiController.addSlider("Noise Decay Spectral Mod", 0.0, -1.0, 1.0, 0);
	
	gGuiController.addSlider("Noise Tone", 0.92, 0.0, 1.0, 0);
	gGuiController.addSlider("Noise Tone Energy Mod", 0.0, -1.0, 1.0, 0);
	gGuiController.addSlider("Noise Tone Spectral Mod", 0.0, -1.0, 1.0, 0);	

	gGuiController.addSlider("Noise Color", 0.75, 0.0, 1.0, 0);
	gGuiController.addSlider("Noise Color Energy Mod", 0.0, -1.0, 1.0, 0);
	gGuiController.addSlider("Noise Color Spectral Mod", 0.0, -1.0, 1.0, 0);
	
	gGuiController.addSlider("Mix Ratio", 0.5, 0.0, 1.0, 0);
	gGuiController.addSlider("Mix Ratio Energy Mod", 0.0, -1.0, 1.0, 0);
	gGuiController.addSlider("Mix Ratio Spectral Mod", 0.0, -1.0, 1.0, 0);

	gGuiController.addSlider("Gain", 0.5, 0.0, 1.0, 0);
	gGuiController.addSlider("Gain Energy Mod", 0.0, -1.0, 1.0, 0);
	gGuiController.addSlider("Gain Spectral Mod", 0.0, -1.0, 1.0, 0);
	
	return true;
}

void render(BelaContext *context, void *userData)
{
	// Whether we should listen and update parameter mapping ranges		
	int listen = static_cast<int>(gGuiController.getSliderValue(0));
	controller.shouldListen(listen);
	
	// Triggering threshold
	float threshold = gGuiController.getSliderValue(1);
	controller.getOnsetDetector().updateParameters(threshold, threshold / 2.0, context->audioSampleRate / 20.0);
	
	// Get synth and mapping parameters from the GUI sliders
	auto& mapping = controller.getParameterMapping();
	for (int i = 0; i < numParams; ++i)
	{
		int index = (i * 3) + paramStartIndex;
		float paramVal = gGuiController.getSliderValue(index);
		float paramModA = gGuiController.getSliderValue(index + 1);
		float paramModB = gGuiController.getSliderValue(index + 2);

		mapping.parameterValues[i] = paramVal;
		mapping.parameterModAmount[i][0] = paramModA;
		mapping.parameterModAmount[i][1] = paramModB;
	}
	
	int numAudioFrames = context->audioFrames;
	for(int n = 0; n < numAudioFrames; n++) {
		// Read from the microphone and process with the synth controller
		float x = audioRead(context, n, 0);
	
		bool triggered = controller.process(x);
		
		// Get the next audio sample from the drum
		float y = drum.process();
		
		// Main audio processing loop
		for(int channel = 0; channel < context->audioOutChannels; channel++){
			audioWrite(context, n, channel, y);
		}
		
#if WATCHING == 1
		uint64_t frames = context->audioFramesElapsed + n;
		Bela_getDefaultWatcherManager()->tick(frames);
		if (triggered) {
			spectralCentroid = controller.getSpectralCentroid();
			onsetEnergy = controller.getOnsetEnergy();
			rt_printf("sc: %f; gain: %f\n", static_cast<float>(spectralCentroid), static_cast<float>(onsetEnergy));
		}
#endif	
	}
}

void cleanup(BelaContext *context, void *userData)
{

}