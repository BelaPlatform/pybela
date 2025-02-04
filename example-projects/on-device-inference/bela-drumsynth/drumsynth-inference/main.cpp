
#include <Bela.h>
#include <iostream>
#include <cstdlib>
#include <cstdio>
#include <csignal>

#include "cxxopts.hpp"
#include "AppOptions.h"

// Handle Ctrl-C by requesting that the audio rendering stop
void interrupt_handler(int var)
{
    Bela_requestStop();
}

AppOptions parseOptions(int argc, char *argv[])
{
    // Parse command-line options
    cxxopts::Options options(
        "pybela DrumSynth",
        "A simple drum synthesizer using PyTorch and Bela."
    );

    options.add_options()
        ("modelPath", "Path to model file", cxxopts::value<std::string>())
        ("h,help", "Print usage")
    ;

    auto result = options.parse(argc, argv);
    if (result.count("help"))
    {
      fprintf(stdout, "%s", options.help().c_str());
      exit(0);
    }

    // create a new AppOptions object
    AppOptions opts;

    if (result.count("modelPath"))
    {
        opts.modelPath = result["modelPath"].as<std::string>();
    }
    else 
    {
        fprintf(stderr, "Error: no model file specified\n");
        exit(1);    
    }

    return opts;
}

int main(int argc, char *argv[])
{
    // Parse command-line options
    AppOptions opts = parseOptions(argc, argv);
    BelaInitSettings *settings = Bela_InitSettings_alloc();

    // Set default settings
    Bela_defaultSettings(settings);
    settings->setup = setup;
    settings->render = render;
    settings->cleanup = cleanup;

    // Set the project name for use in the GUI
    settings->projectName = strrchr(argv[0], '/') + 1;

    // Initialise the PRU audio device
    if (Bela_initAudio(settings, &opts) != 0)
    {
        Bela_InitSettings_free(settings);
        fprintf(stderr, "Error: unable to initialise audio\n");
        return 1;
    }
    Bela_InitSettings_free(settings);


    // Start the audio device running
    if (Bela_startAudio())
    {
        fprintf(stderr, "Error: unable to start real-time audio\n");
        // Stop the audio device
        Bela_stopAudio();
        // Clean up any resources allocated for audio
        Bela_cleanupAudio();
        return 1;
    }

    // Set up interrupt handler to catch Control-C and SIGTERM
    signal(SIGINT, interrupt_handler);
    signal(SIGTERM, interrupt_handler);

    // Run until told to stop
    while (!Bela_stopRequested())
    {
        usleep(100000);
    }

    // Stop the audio device
    Bela_stopAudio();

    // Clean up any resources allocated for audio
    Bela_cleanupAudio();

    // All done!
    return 0;

}