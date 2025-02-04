/**
 * DrumController
 * 
 * Class that takes an incoming audio stream and extracts
 * information to control a drum
 */
 #pragma once

 #include <libraries/ne10/NE10.h>
 #include <vector>
 #include <torch/script.h>

 #include "SnareDrum.h"
 #include "OnsetDetection.h"
 #include "AppOptions.h"
 
 #define ONSET_BUFFER_SIZE 1024	// Circular buffer for onset features
 #define FFT_SIZE 512			// FFT size for onset spectral features
 #define ENERGY_SIZE 128		// Number of samples to use for onset energy calculation
 #define LOOK_BACK 32			// Number of samples before onset to include in calculations
 #define NUM_PARAMS 7			// Total number of synth parameters
 #define NUM_MOD 2				// Total number of modulation sources
 
 
struct DrumParameterMapping {
	std::vector<float> parameterValues;
	std::vector<std::vector<float>> parameterModAmount;
};

class DrumController {
public:
	// Constructor
	DrumController(SnareDrum& d);
	
	void prepare(double sr);
	bool process(float x);
	bool loadModel(AppOptions *opts);
	
	// Getters
	OnsetDetection& getOnsetDetector() { return onset; };
	DrumParameterMapping& getParameterMapping() { return mapping; };
	float getOnsetEnergy() { return onsetEnergy; };
	float getSpectralCentroid() { return spectralCentroid; };
	bool getJustTriggered() { return justTriggered; };
	
	// "Listen" -- updates parameter mapping ranges
	void shouldListen(int listenVal);
	
	// Destructor
	~DrumController();

private:
	double sampleRate;
	SnareDrum& drum;
	OnsetDetection onset;
	DrumParameterMapping mapping;
	
	// Current playing mode	
	enum Mode {
		play,
		listen
	};
	Mode currentMode;
	
	// Circular buffer for saving samples for onset feature processing
	float onsetBuffer[ONSET_BUFFER_SIZE];
	int onsetBufferPointer;
	bool justTriggered;
	bool triggeredDrum;
	int elapsedSamples;
	
	// Attributes for FFT Processing
	ne10_fft_cpx_float32_t* fftIn;
	ne10_fft_cpx_float32_t* fftOut;
	ne10_fft_cfg_float32_t cfg;
	float window[FFT_SIZE];
	
	// Onset features -- updated every onset
	float onsetEnergy;
	float spectralCentroid;
	
	// Ranges, which will be updated after listening
	float onsetEnergyMin;
	float onsetEnergyMax;
	float spectralCentroidMin;
	float spectralCentroidMax;
	
	std::vector<float> onsetEnergyVals;
	std::vector<float> spectralCentroidVals;

	// torch drum mapping model
	torch::jit::script::Module model;
	torch::TensorOptions options;
	
	bool modelLoaded;
	std::vector<float> modelInput;
	std::vector<float> modelOutput;
	
	
	// Private methods for creating audio -> parameter mappings
	
	// Calculate signal energy using numSamples number of samples from the
	// onsetBuffer 
	float getSignalEnergy(int numSamples);
	
	// Calls the FFT and any spectral feature functions
	void updateSpectralParameters();
	
	// Generates a magnitude spectrum from the last FFT_SIZE number
	// of samples in the onsetBuffer. Stores the results in the real portion
	// of the fftOut buffer.
	void processFFT();
	
	// Computes spectral centroid from the magnitude spectrum currently
	// stored in the real portion of fftOut. Stores the result of spectral
	// centroid calculation in spectralCentroid attribute
	void updateSpectralCentroid();
	
	// Computes new parameters and applies them to the drum synthesizer.
	// If trigger is true then will also trigger a new sound.
	void updateSynthParameters(bool trigger);
	
	// Calculate the final value for a synthesis parameter including the
	// modulations from onsetEnergy and spectralCentoid.
	float getModulatedParameterValue(int parameterIndex);

	// Update parameters from the model
	void updateSynthParametersFromModel();
};