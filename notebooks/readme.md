# pyBela notebooks

Prototypes of how the API might look in practice

There are many commonalities between the logger, streamer and monitor (e.g., the querying functions like `.status()`, `.list()` etc.) which suggests that they might all come from the same parent class. This parent class could be Watcher (as a parallelism with the Watcher in Bela).

## Common code to all notebooks:

### In Bela:
Cpp code (applies to the monitor, logger and streamer notebooks):

```cpp
// ~/Bela/projects/watcher-example/render.cpp

bool setup(BelaContext *context, void *userData) {
   watchCh1 = watcher.setupChannel(idx=1, type=int, name="analogFramesElapsed");  
   watchCh2 = watcher.setupChannel(idx=2, type=float, name="sensorValue");
}

void render(BelaContext *context, void *userData){

    for(unsigned int n = 0; n < context->analogFrames; ++n) {

        // log timestamp
        unsigned int analogFramesElapsed = (n + context->audioFramesElapsed) / gAudioFramesPerAnalogFrame;
        watchCh1.log(analogFramesElapsed);

        // log sensor value
        value = analogRead(context, n/gAudioFramesPerAnalogFrame, gSensorChannel);
        watchCh2.log(value)
    }
}
```
