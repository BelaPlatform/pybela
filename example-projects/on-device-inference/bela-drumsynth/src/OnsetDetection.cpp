#include <cmath>

#include "OnsetDetection.h"


OnsetDetection::OnsetDetection() : justTriggered(false), debounce(0), prevValue(0.0)
{
	
}

void OnsetDetection::prepare(double sr)
{
	sampleRate = sr;
	
	// Setting for fast and slow envelope followers
	fastEnv.prepare(3.0, 383.0);
	slowEnv.prepare(2205.0, 2205.0);
	
	// Setup filter
	BiquadCoeff::Settings settings;
	settings.type = BiquadCoeff::highpass;
	settings.fs = sampleRate;
	settings.cutoff = 600.0;
	settings.q = 0.707;
	settings.peakGainDb = 0.0;
	
	hipass.setup(settings);
}


bool OnsetDetection::process(float x)
{
	float diff = onsetSignal(x);
	if (diff > onThreshold && !justTriggered && prevValue < onThreshold && debounce == 0)
	{
		justTriggered = true;
		debounce = waitSamples;
		prevValue = x;
		return true;
	}
	else if (debounce > 0)
	{
		debounce = debounce - 1;
	}
	
	if (debounce == 0 || diff < offThreshold)
	{
		justTriggered = false;
	}
	
	prevValue = x;
	return false;
}

float OnsetDetection::onsetSignal(float x)
{
	// Apply highpass filter
	x = hipass.process(x);
	
	// Rectify, convert to dB, and set minimum value
	x = std::abs(x);
	x = 20.0 * log10f(x);
	x = std::fmax(x, -55.0);
	
	float fast = fastEnv.process(x);
	float slow = slowEnv.process(x);
	float diff = fast - slow;
	
	return diff;
}


void OnsetDetection::updateParameters(float onThresh, float offThresh, int wait)
{
	onThreshold = onThresh;
	offThreshold = offThresh;
	waitSamples = wait;
}
