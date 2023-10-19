#include <Watcher.h>

WatcherManager* Bela_getDefaultWatcherManager()
{
	static Gui gui;
	static WatcherManager defaultWatcherManager(gui);
	return &defaultWatcherManager;
}
