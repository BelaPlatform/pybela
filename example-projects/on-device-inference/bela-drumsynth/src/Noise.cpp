#include <Bela.h>
#include <cstdlib>
#include <cmath>
#include <libraries/math_neon/math_neon.h>

#include "Noise.h"


Noise::Noise() : sampleRate(44100.0), phase(0.0), phaseIncr(0.0), tone(100.0), color(100.0)
{
	updatePhaseIncrHz(440);
}


void Noise::prepare(double sr)
{
	ampDecay.prepare(sr);
	sampleRate = sr;
	
	// Setup filter
	BiquadCoeff::Settings settings;
	settings.type = BiquadCoeff::highpass;
	settings.fs = sampleRate;
	settings.cutoff = tone;
	settings.q = 0.707;
	settings.peakGainDb = 0.0;
	
	filter.setup(settings);
}

void Noise::trigger()
{
	ampDecay.trigger();
}


void Noise::setTone(float newValue)
{
	newValue = powf(newValue, 2.0);
	tone = map(newValue, 0.0, 1.0, 400.0, 1500.0);
	filter.setFc(tone);
}

void Noise::setColor(float newValue)
{
	newValue = powf(newValue, 2.0);
	color = map(newValue, 0.0, 1.0, 0.0, sampleRate / 2.0);
}


void Noise::updatePhaseIncrHz(double hz)
{
	phaseIncr = (hz * 2.0 * M_PI) / sampleRate;
}


float Noise::process()
{
	// Noise modulation signal
	float noiseMod = (2.0 * static_cast<float>(rand()) / RAND_MAX) - 1.0;
	
	// Update the phase increment variable from noise
	updatePhaseIncrHz(tone + noiseMod * color);

	// Get next tonal noise sample
	float y = sinf_neon(phase) * ampDecay.process();
	y = filter.process(y);
	
	// Update and wrap phase
	phase += phaseIncr;
	if (phase >= 2.0 * M_PI)
		phase = phase - 2.0 * M_PI;
	
	return y;
}