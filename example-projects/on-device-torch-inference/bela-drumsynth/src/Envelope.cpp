#include <Bela.h>
#include <cmath>

#include "Envelope.h"


// Constructor
Envelope::Envelope() : sampleRate(44100.0), state(off), currentEnv(0.0)
{

}
	
void Envelope::prepare(double sr)
{
	sampleRate = sr;
	
	// Linear per-sample update for short attack
	attackRate = 1.0 / (0.001 * sampleRate);
}

void Envelope::trigger()
{
	// If the envelope isn't currently running, then reset
	// to zero
	if (state == off) {
		currentEnv = 0.0;
		state = attack;
	} else {
		state = attack;
	}
}

void Envelope::setDecayRate(float newValue)
{
	// Map to seconds
	newValue = powf(newValue, 2.0);
	float secs = map(newValue, 0.0, 1.0, 0.01, 2.0);
	float samples = secs * sampleRate;
	
	// Exponential time constant approx from:
	// https://ccrma.stanford.edu/~jos/pasp/Achieving_Desired_Reverberation_Times.html
	rate = 1.0 - (6.91 / samples);
}


float Envelope::process()
{
	if (state == off)
		return 0.0;
	
	if (state == attack)
	{
		currentEnv += attackRate;
		if (currentEnv >= 1.0)
		{
			currentEnv = 1.0;
			state = decay;
		}
	} 
	else if (state == decay)
	{
		currentEnv = currentEnv * rate;
		if (currentEnv < 0.001) {
			currentEnv = 0.0;
			state = off;
		}
	}
	
	return currentEnv;
}
