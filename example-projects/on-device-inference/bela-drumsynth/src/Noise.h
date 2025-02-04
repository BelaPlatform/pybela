/*
 * Drum Noise Generator
 */
 #pragma once
 
 #include <libraries/Biquad/Biquad.h>

 #include "Envelope.h"

class Noise {
public:
	// constructor
	Noise();
	
	void prepare(double sampleRate);
	
	// Get next sample
	float process();
	
	void trigger();
	
	// Parameter setters
	void setTone(float newValue);
	void setColor(float newValue);
	void setDecay(float newValue) { ampDecay.setDecayRate(newValue); }
	
	// destructor
	~Noise() {};

private:
	double sampleRate;
	float phase;
	float phaseIncr;
	
	float tone;
	float color;
	
	Envelope ampDecay;
	Biquad filter;
	
	void updatePhaseIncrHz(double hz);
};