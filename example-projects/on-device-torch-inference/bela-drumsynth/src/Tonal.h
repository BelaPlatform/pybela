/**
 * Class for generating tonal component of drum sounds
 */
#pragma once

#include "Envelope.h"

class Tonal {
public:

	// Constructor
	Tonal();

	void prepare(double rate);
	float process();
	void trigger();
	
	// Parameter settters
	void setDecay(float newValue);
	void setTuning(float newValue);
	
	// Destructor
	~Tonal() {};

private:
	double sampleRate;
	float tuning;
	
	float phase;
	float phaseIncr;
	
	Envelope pitchEnvelope;
	Envelope ampEnvelope;
};