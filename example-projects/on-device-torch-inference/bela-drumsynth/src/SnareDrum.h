/**
 * Snare Drum Synth Class
 */
#pragma once

#include "Noise.h"
#include "Tonal.h"


class SnareDrum {
public:
	// Constructor
	SnareDrum() {};
	
	void prepare(double sampleRate);
	
	// Get the next sample
	float process();
	
	void trigger();
	void trigger(float velocity);
	
	// Get a reference to the processors
	Noise& getNoise() { return noise; };
	Tonal& getTonal() { return tonal; };
	
	// Parameter setters
	void setMixRatio(float newValue);
	void setGain(float newValue);
	
	float getGain() { return gain; };
	float getMix() { return mix; };
	
	// Deconstructor
	~SnareDrum() {};
	
	

private:
	Noise noise;
	Tonal tonal;
	
	float mix;
	float gain;
};