#include <Bela.h>
#include <cmath>
#include <iostream>
#include <algorithm>

#include "DrumController.h"



DrumController::DrumController(SnareDrum& d) 
: sampleRate(44100.0), drum(d), currentMode(play), justTriggered(false), triggeredDrum(false), elapsedSamples(0)
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
		updateSynthParameters(true);
		triggeredDrum = true;
	}
	
	// Wait longer to do the spectral processing for parameter adjustments
	if (justTriggered && elapsedSamples >= FFT_SIZE - LOOK_BACK)
	{
		// Do spectral analysis and mapping
		updateSpectralParameters();
		updateSynthParameters(false);
		justTriggered = false;
		onsetUpdate = true;
	}
	
	
	++elapsedSamples;
	
	return onsetUpdate;
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