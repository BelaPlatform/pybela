/*
 * Simple Exponential Decay Envelope
 */
#pragma once

enum EnvState { off, attack, decay };

class Envelope {
public:
	// Constructor
	Envelope();
	
	void prepare(double sr);
	float process();
	void trigger();
	
	// Parameter setter
	void setDecayRate(float newValue);
	
	// Destructor
	~Envelope() {};

private:
	double sampleRate;
	
	EnvState state;
	float rate;
	float attackRate;
	float currentEnv;
};
