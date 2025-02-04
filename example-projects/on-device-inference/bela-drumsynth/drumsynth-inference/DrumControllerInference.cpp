#include <Bela.h>
#include <cmath>
#include <iostream>
#include <algorithm>

#include "DrumControllerInference.h"



DrumController::DrumController(SnareDrum& d) 
: sampleRate(44100.0), drum(d), currentMode(play), justTriggered(false), triggeredDrum(false), elapsedSamples(0), modelLoaded(false)
{
	// Initialize memory for FFT
	fftIn = (ne10_fft_cpx_float32_t*) NE10_MALLOC (FFT_SIZE * sizeof (ne10_fft_cpx_float32_t));
	fftOut = (ne10_fft_cpx_float32_t*) NE10_MALLOC (FFT_SIZE * sizeof (ne10_fft_cpx_float32_t));
	cfg = ne10_fft_alloc_c2c_float32_neon (FFT_SIZE);
	
	// Initialize Hann window
	for (int n = 0; n < FFT_SIZE; n++)
	{
		window[n] = 0.5 * (1.0 - cosf((2.0 * M_PI * n) / (float)(FFT_SIZE - 1)));
	}
	
	// Initialize onset features
	spectralCentroid = 0.0;
	onsetEnergy = 0.0;
	
	onsetEnergyMin = 0.0;
	onsetEnergyMax = 0.0;
	spectralCentroidMin = 0.0;
	spectralCentroidMax = 0.0;
	
	// Initalize mapping
	for (int i = 0; i < NUM_PARAMS; ++i)
	{
		mapping.parameterValues.push_back(0.0f);
		mapping.parameterModAmount.emplace_back();
		for (int j = 0; j < NUM_MOD; ++j)
		{
			mapping.parameterModAmount[i].push_back(0.0f);
		}
	}

	// Torch Tensor options
    options = torch::TensorOptions()
        .dtype(torch::kFloat32)
        .device(torch::kCPU)
        .requires_grad(false);
}

DrumController::~DrumController()
{
	// Free memory initialized for FFT
	NE10_FREE(fftIn);
	NE10_FREE(fftOut);
	NE10_FREE(cfg);
}


void DrumController::prepare(double sr)
{
	sampleRate = sr;
	onset.prepare(sampleRate);
	
	onsetBufferPointer = 0;
	for (int i = 0; i < ONSET_BUFFER_SIZE; ++i)
		onsetBuffer[i] = 0.0;
		
	// Reset trigger vars
	justTriggered = false;
	triggeredDrum = false;
	elapsedSamples = 0;
}


bool DrumController::process(float x)
{
	// Perform onset detection on incoming signal and trigger drum
	bool onsetUpdate = false;
	bool shouldTrigger = onset.process(x);
	if (shouldTrigger)
	{
		justTriggered = true;
		triggeredDrum = false;
		elapsedSamples = 0;
	}
	
	// Store sample in buffer
	onsetBuffer[onsetBufferPointer] = x;
	if (++onsetBufferPointer >= ONSET_BUFFER_SIZE)
		onsetBufferPointer = 0;
		
	
	// Wait until the correct number of samples for the energy calculation have been
	// accumulated. Compute onset energy and then trigger the new drum sound.
	if (justTriggered && elapsedSamples >=  ENERGY_SIZE - LOOK_BACK && !triggeredDrum)
	{
		onsetEnergy = getSignalEnergy(ENERGY_SIZE);
		// Don't trigger the drum here -- wait until the spectral processing is done
		// updateSynthParameters(true);
		triggeredDrum = true;
	}
	
	// Wait longer to do the spectral processing for parameter adjustments
	if (justTriggered && elapsedSamples >= FFT_SIZE - LOOK_BACK)
	{
		// Do spectral analysis and mapping -- update synth parameters and trigger drum
		updateSpectralParameters();
		updateSynthParameters(true);
		justTriggered = false;
		onsetUpdate = true;
	}
	
	
	++elapsedSamples;
	
	return onsetUpdate;
}

bool DrumController::loadModel(AppOptions *opts)
{
	try {
        model = torch::jit::load(opts->modelPath.c_str());
		std::cerr << "Model loaded successfully" << std::endl;
    } catch (const c10::Error& e) {
        std::cerr << "Error loading the model: " << e.msg() << std::endl;
        return false;
    }

	// Initialize input and output tensors
	modelInput.resize(2);
	modelOutput.resize(7);
	
	// Prepare the model
	model.eval();

	modelLoaded = true;
	return true;
}

void DrumController::shouldListen(int listenVal)
{
	if (listenVal == 1 && currentMode == play)
	{
		// Start listening
		onsetEnergyVals.clear();
		spectralCentroidVals.clear();
		currentMode = listen;
	}
	else if (listenVal == 0 && currentMode == listen)
	{
		// update min and max values for each feature
		auto minmaxEnergy = std::minmax_element(onsetEnergyVals.begin(), onsetEnergyVals.end());
		onsetEnergyMin = *minmaxEnergy.first;
		onsetEnergyMax = *minmaxEnergy.second;
		
		auto minmaxSC = std::minmax_element(spectralCentroidVals.begin(), spectralCentroidVals.end());
		spectralCentroidMin = *minmaxSC.first;
		spectralCentroidMax = *minmaxSC.second;
		
		currentMode = play;
	}
}


float DrumController::getSignalEnergy(int numSamples)
{
	float energy = 0;
	int index = onsetBufferPointer - numSamples;
	if (index < 0)
		index += ONSET_BUFFER_SIZE;
	
	for (int i = 0; i < numSamples; ++i)
	{
		energy += onsetBuffer[index] * onsetBuffer[index];
		if (++index >= ONSET_BUFFER_SIZE)
			index = 0;
		
	}
	energy = energy / static_cast<float>(numSamples);
	return energy;
}

void DrumController::updateSpectralParameters()
{
	processFFT();
	updateSpectralCentroid();
}

void DrumController::processFFT()
{
	// Copy samples from onset buffer into FFT buffer
	int index = onsetBufferPointer - FFT_SIZE;
	if (index < 0)
		index += ONSET_BUFFER_SIZE;
	
	for (int n = 0; n < FFT_SIZE; ++n)
	{
		fftIn[n].r = (ne10_float32_t) onsetBuffer[index] * window[n];
		fftIn[n].i = 0.0;

		if (++index >= ONSET_BUFFER_SIZE)
			index = 0;
	}
	
	// Run the FFT
	ne10_fft_c2c_1d_float32_neon (fftOut, fftIn, cfg, 0);
	
	// Convert to magnitude spectrum
	for (int n = 0; n < FFT_SIZE; ++n)
	{
		float amplitude = sqrtf(fftOut[n].r * fftOut[n].r + fftOut[n].i * fftOut[n].i);
		
		// Saving the magnitude spectrum to the real component of the fftOut buffer
		// Not worrying about phase here
		fftOut[n].r = amplitude;
 	}
}

void DrumController::updateSpectralCentroid()
{
	// Calculate spectral centroid based on current frequency magnitude buffer
	float weightedSum = 0.0;
	float norm = 0.0;
	for (int n = 0; n < (FFT_SIZE / 2) + 1; n++)
	{
		weightedSum += n * fftOut[n].r;
		norm += fftOut[n].r;
	}
	
	spectralCentroid = weightedSum / norm;
}


void DrumController::updateSynthParameters(bool trigger)
{
	// Update synth parameters based on current values
	if (currentMode == listen) 
	{
		// Store onset values if not triggering (i.e., delayed spectral values)
		if (!trigger)
		{
			onsetEnergyVals.push_back(onsetEnergy);
			spectralCentroidVals.push_back(spectralCentroid);
		}
		return;
	}

	rt_printf("Spectral Centroid: %f, Onset Energy: %f\n", spectralCentroid, onsetEnergy);
	
	// Use the neural network if it is loaded
	if (modelLoaded)
	{
		updateSynthParametersFromModel();
		drum.trigger();
		return;
	}

	auto& tonal = drum.getTonal();
	tonal.setDecay(getModulatedParameterValue(0));
	tonal.setTuning(getModulatedParameterValue(1));
	
	auto& noise = drum.getNoise();
	noise.setDecay(getModulatedParameterValue(2));
	noise.setTone(getModulatedParameterValue(3));
	noise.setColor(getModulatedParameterValue(4));
	
	drum.setMixRatio(getModulatedParameterValue(5));
	drum.setGain(getModulatedParameterValue(6));
	
	// Trigger if necessary
	if (trigger)
		drum.trigger();
}

float DrumController::getModulatedParameterValue(int parameterIndex)
{
	// Energy modulation -- calculate modulation amount for this parameter
	float energyMod = 0.0;
	if (onsetEnergyMax > 0.0 && onsetEnergyMax > onsetEnergyMin)
	{
		float energyModAmount = mapping.parameterModAmount[parameterIndex][0];
		energyMod = constrain(onsetEnergy, onsetEnergyMin, onsetEnergyMax);
		energyMod = map(energyMod, onsetEnergyMin, onsetEnergyMax, 0.0, std::abs(energyModAmount));
		
		// Handle negative modulations
		if (energyModAmount < 0.0)
			energyMod *= -1.0;
	}

	// Spectral modulation
	float spectralMod = 0.0;
	if (spectralCentroidMax > 0.0 && spectralCentroidMax > spectralCentroidMin)
	{
		float spectralModAmount = mapping.parameterModAmount[parameterIndex][1];
		spectralMod = constrain(spectralCentroid, spectralCentroidMin, spectralCentroidMax);
		spectralMod = map(spectralMod, spectralCentroidMin, spectralCentroidMax, 0.0, std::abs(spectralModAmount));
		if (spectralModAmount < 0.0)
			spectralMod *= -1.0;
	}

	// Base parameter value plus modulations
	float value = mapping.parameterValues[parameterIndex] + energyMod + spectralMod;
	return constrain(value, 0.0, 1.0);
}

void DrumController::updateSynthParametersFromModel()
{
	// Prepare input for model
	modelInput[0] = spectralCentroid;
	modelInput[1] = onsetEnergy;

	// Convert input to tensor
    torch::Tensor inputTensor = torch::from_blob(modelInput.data(), {1, 2}).clone();

	// Perform inference
    torch::Tensor outputTensor = model.forward({inputTensor}).toTensor();
    outputTensor = outputTensor.view(-1);

	// Copy outputTensor to outBuffer
    for (int n = 0; n < 7; n++) {
		modelOutput[n] = outputTensor[n].item<float>();
    }

	// Update synth parameters
	auto& tonal = drum.getTonal();
	tonal.setDecay(modelOutput[0]);
	tonal.setTuning(modelOutput[1]);
	
	auto& noise = drum.getNoise();
	noise.setDecay(modelOutput[2]);
	noise.setTone(modelOutput[3]);
	noise.setColor(modelOutput[4]);
	
	drum.setMixRatio(modelOutput[5]);
	drum.setGain(modelOutput[6]);
}
