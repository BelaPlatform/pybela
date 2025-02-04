#include <Bela.h>
#include <cmath>
#include <libraries/math_neon/math_neon.h>

#include "Tonal.h"

// Constructor
Tonal::Tonal() : sampleRate(44100), tuning(100.0), phase(0.0), phaseIncr(0.0)
{
	
}


void Tonal::prepare(double rate)
{
	pitchEnvelope.prepare(rate);
	ampEnvelope.prepare(rate);
	
	sampleRate = rate;
}


float Tonal::process()
{
	float y = sinf_neon(phase);
	float pitchAmount = pitchEnvelope.process() * 4.0 + 1.0;
	phase += phaseIncr * pitchAmount;
	if (phase >= 2*M_PI)
		phase = phase - 2*M_PI;
	
	return y * ampEnvelope.process();
}


void Tonal::trigger()
{
	pitchEnvelope.trigger();
	ampEnvelope.trigger();
}


// Parameter settters
void Tonal::setDecay(float newValue)
{
	pitchEnvelope.setDecayRate(newValue * 0.3);
	ampEnvelope.setDecayRate(newValue * 0.9);
}


void Tonal::setTuning(float newValue)
{
	newValue = powf(newValue, 2.0);
	tuning = map(newValue, 0.0, 1.0, 20, 400);
	phaseIncr = 2.0 * M_PI * tuning / sampleRate;
}