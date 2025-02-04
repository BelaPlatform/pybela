#include <cmath>
#include <Bela.h>

#include "SnareDrum.h"


void SnareDrum::prepare(double sampleRate)
{
	noise.prepare(sampleRate);
	tonal.prepare(sampleRate);
	
	mix = 0.5;
	gain = 0.5;
}

void SnareDrum::trigger()
{
	noise.trigger();
	tonal.trigger();
}


void SnareDrum::trigger(float velocity)
{
	noise.setTone(velocity);
	noise.setDecay(velocity);
	noise.trigger();
	tonal.trigger();
}


float SnareDrum::process()
{	
	float tonalLevel = sqrtf(mix);
	float noiseLevel = sqrtf(1.0 - mix);
	
	float y = noiseLevel * noise.process() + tonalLevel * tonal.process();
	return tanh(y * gain);
}

void SnareDrum::setMixRatio(float newValue)
{
	mix = constrain(newValue, 0.0, 1.0);
}

void SnareDrum::setGain(float newValue)
{
	float gainDB = map(newValue, 0.0, 1.0, -36.0, 24.0);
	gain = powf(10.0, gainDB / 20.0);
}

