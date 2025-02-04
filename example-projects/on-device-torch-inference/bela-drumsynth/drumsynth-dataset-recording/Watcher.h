#pragma once

#include <vector>
#include <typeinfo>
#include <string>
#include <new> // for std::bad_alloc
#include <unistd.h>
#include <atomic>
#include <libraries/Pipe/Pipe.h>

class WatcherManager;
class WatcherBase {
public:
	void localControl(bool enable) {
		if(localControlEnabled != enable)
		{
			localControlEnabled = enable;
			localControlChanged();
		}
	}
	virtual double wmGet() = 0;
	virtual double wmGetInput() = 0;
	virtual void wmSet(double) = 0;
	virtual void wmSetMask(unsigned int, unsigned int) = 0;
	virtual void localControlChanged() {}
	bool hasLocalControl() {
		return localControlEnabled;
	}
protected:
	bool localControlEnabled = true;
};

#include <algorithm>
#include <vector>
#include <libraries/Gui/Gui.h>
#include <libraries/WriteFile/WriteFile.h>

static inline const JSONArray& JSONGetArray(JSONObject& root, const std::string& key)
{
	static const JSONArray empty;
	std::wstring ws = JSON::s2ws(key);
	if(root.find(ws) == root.end())
		return empty;
	if(!root[ws]->IsArray())
		return empty;
	return root[ws]->AsArray();
}
static inline const JSONArray& JSONGetArray(JSONValue* el, const std::string& key)
{
	static const JSONArray empty;
	std::wstring ws = JSON::s2ws(key);
	const wchar_t* wkey = ws.c_str();
	if(el->HasChild(wkey) && el->Child(wkey)->IsArray())
		return el->Child(wkey)->AsArray();
	else
		return empty;
}

static inline std::string JSONGetAsString(JSONValue* el)
{
	if(el->IsString())
		return JSON::ws2s(el->AsString());
	else
		return "";
}

static inline std::string JSONGetString(JSONValue* el, const std::string& key)
{
	std::wstring ws = JSON::s2ws(key);
	const wchar_t* wkey = ws.c_str();
	if(el->HasChild(wkey))
		return JSONGetAsString(el->Child(wkey));
	else
		return "";
}

static inline double JSONGetAsNumber(JSONValue* el)
{
	if(el->IsNumber())
		return el->AsNumber();
	else if(el->IsBool())
		return el->AsBool();
	else
		return 0;
}
template <typename T>
static inline double _JSONGetNumber(JSONValue* el, const T& key)
{
	if(el->HasChild(key))
	{
		JSONValue* child = el->Child(key);
		return JSONGetAsNumber(child);
	}
	return 0;
}
static inline double JSONGetNumber(JSONValue* el, size_t key)
{
	return _JSONGetNumber(el, key);
}

// the below is deprecated because it's probably broken:
// JSONValue will destroy arr (or its contents?) not sure, so test it  before use
static inline double JSONGetNumber(const JSONArray& arr, size_t key) __attribute__ ((deprecated("Not actually deprecated, but probably broken. Needs testing")));
static inline double JSONGetNumber(const JSONArray& arr, size_t key)
{
	JSONValue value(arr);
	return _JSONGetNumber(&value, key);
}

static inline double JSONGetNumber(JSONValue* el, const std::string& key)
{
	std::wstring ws = JSON::s2ws(key);
	const wchar_t* wkey = ws.c_str();
	return _JSONGetNumber(el, wkey);
}

#include <thread>
class WatcherManager
{
	static constexpr uint32_t kMonitorDont = 0;
	static constexpr uint32_t kMonitorChange = 1 << 31;
	typedef uint64_t AbsTimestamp;
	typedef uint32_t RelTimestamp;
	struct Priv;
	std::thread pipeToJsonThread;
	AbsTimestamp timestamp = 0;
	size_t pipeReceivedRt = 0;
	size_t pipeSentNonRt = 0;
	Pipe pipe;
	volatile bool shouldStop;
	static constexpr size_t kMsgHeaderLength = sizeof(timestamp);
	static_assert(0 == kMsgHeaderLength % sizeof(float), "has to be multiple");
	static constexpr size_t kBufSize = 4096 + kMsgHeaderLength;
	static size_t getRelTimestampsOffset(size_t dataSize)
	{
		size_t maxElements = (kBufSize - kMsgHeaderLength) / (dataSize + sizeof(RelTimestamp));
		size_t offset = maxElements * dataSize + kMsgHeaderLength;
		// round down to nearest aligned byte
		offset = offset & ~(sizeof(RelTimestamp) - 1);
		return offset;
	}
public:
	WatcherManager(Gui& gui) : pipe("watcherManager", 65536, true, true), gui(gui)
	{
		gui.setControlDataCallback([this](JSONObject& json, void*) {
			this->controlCallback(json);
			return true;
		});
		pipe.setTimeoutMsNonRt(100);
		shouldStop = false;
		pipeToJsonThread = std::thread(&WatcherManager::pipeToJson, this);
	};
	~WatcherManager()
	{
		shouldStop = true;
		pipeToJsonThread.join();
	}
	void setup(float sampleRate)
	{
		this->sampleRate = sampleRate;
	}
	class Details;
	enum TimestampMode {
		kTimestampBlock,
		kTimestampSample,
	};
	template <typename T>
	Details* reg(WatcherBase* that, const std::string& name, TimestampMode timestampMode)
	{
		vec.emplace_back(new Priv{
			.w = that,
			.count = 0,
			.name = name,
			.guiBufferId = gui.setBuffer(*typeid(T).name(), kBufSize),
			.logger = nullptr,
			.type = typeid(T).name(),
			.timestampMode = timestampMode,
			.firstTimestamp = 0,
			.relTimestampsOffset = getRelTimestampsOffset(sizeof(T)),
			.countRelTimestamps = 0,
			.monitoring = kMonitorDont,
			.controlled = false,
		});
		Priv* p = vec.back();
		p->v.resize(kBufSize); // how do we include this above?
		if(((uintptr_t)p->v.data() + kMsgHeaderLength) & (sizeof(T) - 1))
			throw(std::bad_alloc());
		p->maxCount = kTimestampBlock == p->timestampMode ? p->v.size() : p->relTimestampsOffset - (sizeof(T) - 1);
		updateSometingToDo(p);
		return (Details*)vec.back();
	}
	void unreg(WatcherBase* that)
	{
		auto it = std::find_if(vec.begin(), vec.end(), [that](decltype(vec[0])& item){
			return item->w == that;
		});
		cleanupLogger(*it);
		// TODO: unregister from GUI
		delete *it;
		vec.erase(it);
	}
	void tick(AbsTimestamp frames, bool full = true)
	{
		timestamp = frames;
		if(!full)
			return;
		while(pipeReceivedRt != pipeSentNonRt)
		{
			MsgToRt msg;
			if(1 == pipe.readRt(msg))
			{
				pipeReceivedRt++;
				switch(msg.cmd)
				{
					case MsgToRt::kCmdStartLogging:
						startLogging(msg.priv, msg.args[0], msg.args[1]);
						break;
					case MsgToRt::kCmdStopLogging:
						stopLogging(msg.priv, msg.args[0]);
						break;
					case MsgToRt::kCmdStartWatching:
						startWatching(msg.priv, msg.args[0], msg.args[1]);
						break;
					case MsgToRt::kCmdStopWatching:
						stopWatching(msg.priv, msg.args[0]);
						break;
					case MsgToRt::kCmdNone:
						break;
				}
			} else {
				rt_fprintf(stderr, "Error: missing messages in the pipe\n");
				pipeReceivedRt = pipeSentNonRt;
			}
		}
		clientActive = gui.numActiveConnections();
	}
	void updateSometingToDo(Priv* p, bool should = false)
	{
		for(auto& stream : p->streams)
		{
			should |= (stream.schedTsStart != -1);
			should |= stream.state;
		}
		should |= (kMonitorDont != p->monitoring);
		// TODO: is watching should be conditional to && clientActive,
		// but for that to work, we'd need to call this for each client
		// on clientActive change, which could be very expensive
		should |= (isStreaming(p, kStreamIdxWatch)) || isStreaming(p, kStreamIdxLog);
		p->somethingToDo = should;
	}
	// the relevant object is passed back here so that we don't have to waste
	// time looking it up
	template <typename T>
	void notify(Details* d, const T& value)
	{
		Priv* p = reinterpret_cast<Priv*>(d);
		if(!p)
			return;
		if(!p->somethingToDo)
			return;
		bool streamLast = false;
		for(auto& stream : p->streams)
		{
			if(timestamp >= stream.schedTsStart)
			{
				stream.schedTsStart = -1;
				if(kStreamStateStarting == stream.state)
				{
					stream.state = kStreamStateYes;
					// TODO: watching and logging use the same buffer,
					// so you'll get a dropout in the watching if you
					// are watching right now
					p->count = 0;
					if(-1 != stream.schedTsEnd) {
						// if an end timestamp is provided,
						// schedule the end immediately
						stream.schedTsStart = stream.schedTsEnd;
						stream.state = kStreamStateStopping;
					}
				}
				else if(kStreamStateStopping == stream.state)
				{
					stream.state = kStreamStateLast;
					streamLast = true;
				}
				updateSometingToDo(p);
			}
		}
		if(kMonitorDont != p->monitoring)
		{
			if(p->monitoring & kMonitorChange)
			{
				p->monitoring &= ~kMonitorChange; // reset flag
				if(p->monitoring) {
					// trigger to send one immediately
					p->monitoringNext = timestamp;
				} else
					p->monitoringNext = -1;
			}
			if(timestamp >= p->monitoringNext)
			{
				if(clientActive)
				{
					// big enough for the timestamp and one value
					// and possibly some padding bytes at the end
					// (though in practice there won't be any when
					// sizeof(T) <= kMsgHeaderLength)
					uint8_t data[((kMsgHeaderLength + sizeof(value) + sizeof(T) - 1) / sizeof(T)) * sizeof(T)];
					memcpy(data, &timestamp, kMsgHeaderLength);
					memcpy(data + kMsgHeaderLength, &value, sizeof(value));
					gui.sendBuffer(p->guiBufferId, (T*)data, sizeof(data) / sizeof(T));
				}
				if(1 == p->monitoring)
				{
					// special case: one-shot
					// so disable at the next iteration
					p->monitoring = kMonitorChange | 0;
					updateSometingToDo(p);
				} else
					p->monitoringNext = timestamp + p->monitoring;
			}
		}
		if((isStreaming(p, kStreamIdxWatch) && clientActive) || isStreaming(p, kStreamIdxLog))
		{
			if(0 == p->count)
			{
				memcpy(p->v.data(), &timestamp, kMsgHeaderLength);
				p->firstTimestamp = timestamp;
				p->count += kMsgHeaderLength;
				p->countRelTimestamps = p->relTimestampsOffset;
			}
			*(T*)(p->v.data() + p->count) = value;
			p->count += sizeof(value);
			bool full = p->count >= p->maxCount;
			if(kTimestampSample == p->timestampMode)
			{
				// we have two arrays: one of type T starting
				// at kMsgHeaderLength and one of type
				// RelTimestamp starting at relTimestampsOffset
				RelTimestamp relTimestamp = timestamp - p->firstTimestamp;
				*(RelTimestamp*)(p->v.data() + p->countRelTimestamps) = relTimestamp;
				p->countRelTimestamps += sizeof(relTimestamp);
				full |= (p->count >= p->relTimestampsOffset || p->countRelTimestamps >= p->v.size());
			} else {
				// only one array of type T starting at
				// kMsgHeaderLength
			}
			if(full || streamLast)
			{
				if(!full)
				{
					// when logging stops, we need to fill
					// up all the remaining space with zeros
					// TODO: remove this when we support
					// variable-length blocks
					if(kTimestampSample == p->timestampMode)
					{
						memset(p->v.data() + p->count, 0, p->relTimestampsOffset - p->count);
						memset(p->v.data() + p->countRelTimestamps, 0, p->v.size() - p->countRelTimestamps);
					} else
						memset(p->v.data() + p->count, 0, p->v.size() - p->count);
				}
				// TODO: in order to even out the CPU load,
				// incoming data should be copied out of the
				// audio thread one value at a time
				// avoiding big copies like this one
				// OTOH, we'll need to ensure only full blocks
				// are sent so that we don't lose track of the
				// header

				send<T>(p);
				bool shouldUpdate = false;
				for(size_t n = 0; n < p->streams.size(); ++n)
				{
					Stream& stream = p->streams[n];
					if(kStreamStateLast == stream.state)
					{
						if(kStreamIdxLog == n)
							p->logger->requestFlush();
						stream.state = kStreamStateNo;
						shouldUpdate = true;
					}
				}
				if(shouldUpdate)
					updateSometingToDo(p);
				p->count = 0;
			}
		}
	}
	Gui& getGui() {
		return gui;
	}
private:
	enum StreamIdx {
		kStreamIdxLog,
		kStreamIdxWatch,
		kStreamIdxNum,
	};
	enum StreamState {
		kStreamStateNo,
		kStreamStateStarting,
		kStreamStateYes,
		kStreamStateStopping,
		kStreamStateLast,
	};
	struct Stream {
		AbsTimestamp schedTsStart = -1;
		AbsTimestamp schedTsEnd = -1;
		StreamState state = kStreamStateNo;
	};
	struct Priv {
		WatcherBase* w;
		std::vector<unsigned char> v;
		size_t count;
		std::string name;
		unsigned int guiBufferId;
		WriteFile* logger;
		std::string logFileName;
		const char* type;
		TimestampMode timestampMode;
		AbsTimestamp firstTimestamp;
		size_t relTimestampsOffset;
		size_t countRelTimestamps;
		size_t maxCount;
		uint32_t monitoring;
		AbsTimestamp monitoringNext;
		std::array<Stream,kStreamIdxNum> streams;
		bool controlled;
		bool somethingToDo;
	};
	struct MsgToNrt {
		Priv* priv;
		enum Cmd {
			kCmdNone,
			kCmdStartedLogging,
		} cmd;
		uint64_t args[2];
	};
	struct MsgToRt {
		Priv* priv;
		enum Cmd {
			kCmdNone,
			kCmdStartLogging,
			kCmdStopLogging,
			kCmdStartWatching,
			kCmdStopWatching,
		} cmd;
		uint64_t args[2];
	};
	void pipeToJson()
	{
		while(!shouldStop)
		{
			struct MsgToNrt msg;
			if(1 == pipe.readNonRt(msg))
			{
				switch(msg.cmd)
				{
					case MsgToNrt::kCmdStartedLogging:
					{
						JSONObject watcher;
						watcher[L"watcher"] = new JSONValue(JSON::s2ws(msg.priv->name));
						watcher[L"logFileName"] = new JSONValue(JSON::s2ws(msg.priv->logFileName));
						watcher[L"timestamp"] = new JSONValue(double(msg.args[0]));
						watcher[L"timestampEnd"] = new JSONValue(double(msg.args[1]));
						sendJsonResponse(new JSONValue(watcher), WSServer::kThreadOther);
					}
						break;
					case MsgToNrt::kCmdNone:
						break;
				}
			}
		}
	}
	bool isStreaming(const Priv* p, StreamIdx idx) const
	{
		StreamState state = p->streams[idx].state;
		return kStreamStateYes == state || kStreamStateStopping == state|| kStreamStateLast == state;
	}
	template <typename T>
	void send(Priv* p) {
		size_t size = p->v.size(); // TODO: customise this for smaller frames
		if(clientActive && isStreaming(p, kStreamIdxWatch))
			gui.sendBuffer(p->guiBufferId, (T*)p->v.data(), size / sizeof(T));
		if(isStreaming(p, kStreamIdxLog))
			p->logger->log((float*)p->v.data(), size / sizeof(float));
	}
	void startWatching(Priv* p, AbsTimestamp startTimestamp, AbsTimestamp duration) {
		startStreamAtFor(p, kStreamIdxWatch, startTimestamp, duration);
		// TODO: register guiBufferId here
	}
	void stopWatching(Priv* p, AbsTimestamp timestampEnd) {
		stopStreamAt(p, kStreamIdxWatch, timestampEnd);
		// TODO: unregister guiBufferId here
	}
	void startControlling(Priv* p) {
		if(p->controlled)
			return;
		p->controlled = true;
		p->w->localControl(false);
	}
	void stopControlling(Priv* p) {
		if(!p->controlled)
			return;
		p->controlled = false;
		p->w->localControl(true);
	}
	void startStreamAtFor(Priv* p, StreamIdx idx, AbsTimestamp startTimestamp, AbsTimestamp duration) {
		Stream& stream = p->streams[idx];
		stream.state = kStreamStateStarting;
		if(startTimestamp < timestamp)
			startTimestamp = timestamp;
		stream.schedTsStart = startTimestamp;
		AbsTimestamp timestampEnd = startTimestamp + duration;
		if(0 == duration)
			timestampEnd = -1; // do not stop automatically
		stream.schedTsEnd = timestampEnd;
		if(kStreamIdxLog == idx) {
			// send a response with the actual timestamps
			MsgToNrt msg {
				.priv = p,
				.cmd = MsgToNrt::kCmdStartedLogging,
				.args = {
					startTimestamp,
					timestampEnd,
				},
			};
			pipe.writeRt(msg);
		}
		updateSometingToDo(p, true);
	}
	void stopStreamAt(Priv* p, StreamIdx idx, AbsTimestamp timestampEnd) {
		Stream& stream = p->streams[idx];
		if(kStreamStateNo == stream.state)
			return;
		stream.state = kStreamStateStopping;
		stream.schedTsStart = timestampEnd;
		updateSometingToDo(p, true);
	}
	void startLogging(Priv* p, AbsTimestamp startTimestamp, AbsTimestamp duration) {
		startStreamAtFor(p, kStreamIdxLog, startTimestamp, duration);
	}
	void stopLogging(Priv* p, AbsTimestamp timestamp) {
		stopStreamAt(p, kStreamIdxLog, timestamp);
	}
	void setMonitoring(Priv* p, size_t period) {
		p->monitoring = (kMonitorChange | period);
		p->somethingToDo = true; // TODO: race condition
	}
	void setupLogger(Priv* p) {
		cleanupLogger(p);
		p->logger = new WriteFile((p->name + ".bin").c_str(), false, false);
		p->logger->setFileType(kBinary);
		p->logFileName = p->logger->getName();
		std::vector<uint8_t> header;
		// string fields first, null-separated
		for(auto c : std::string("watcher"))
			header.push_back(c);
		header.push_back(0);
		for(auto c : p->name)
			header.push_back(c);
		header.push_back(0);
		for(auto c : std::string(p->type))
			header.push_back(c);
		header.push_back(0);
		pid_t pid = getpid();
		for(size_t n = 0; n < sizeof(pid); ++n)
			header.push_back(((uint8_t*)&pid)[n]);
		decltype(this) ptr = this;
		for(size_t n = 0; n < sizeof(ptr); ++n)
			header.push_back(((uint8_t*)&ptr)[n]);
		header.resize(((header.size() + 3) / 4) * 4); // round to nearest multiple of 4
		p->logger->log((float*)(header.data()), header.size() / sizeof(float));
	}

	void cleanupLogger(Priv* p) {
		if(!p || !p->logger)
			return;
		p->logger->cleanup(false);
		delete p->logger;
		p->logger = nullptr;
	}

	Priv* findPrivByName(const std::string& str) {
		auto it = std::find_if(vec.begin(), vec.end(), [&str](decltype(vec[0])& item) {
			return item->name == str;
		});
		if(it != vec.end())
			return *it;
		else
			return nullptr;
	}
	void sendJsonResponse(JSONValue* watcher, WSServer::CallingThread thread)
	{
		// should be called from the controlCallback() thread
		JSONObject root;
		root[L"watcher"] = watcher;
		JSONValue value(root);
		gui.sendControl(&value, thread);
	}
	bool controlCallback(JSONObject& root) {
		auto watcher = JSONGetArray(root, "watcher");
		for(size_t n = 0; n < watcher.size(); ++n)
		{
			JSONValue* el = watcher[n];
			std::string cmd = JSONGetString(el, "cmd");
			if("list" == cmd)
			{
				// send watcher list JSON
				JSONArray watchers;
				for(auto& item : vec)
				{
					auto& v = *item;
					JSONObject watcher;
					watcher[L"name"] = new JSONValue(JSON::s2ws(v.name));
					watcher[L"watched"] = new JSONValue(isStreaming(&v, kStreamIdxWatch));
					watcher[L"controlled"] = new JSONValue(v.controlled);
					watcher[L"logged"] = new JSONValue(isStreaming(&v, kStreamIdxLog));
					watcher[L"monitor"] = new JSONValue(int((~kMonitorChange) & v.monitoring));
					watcher[L"logFileName"] = new JSONValue(JSON::s2ws(v.logFileName));
					watcher[L"value"] = new JSONValue(v.w->wmGet());
					watcher[L"valueInput"] = new JSONValue(v.w->wmGetInput());
					watcher[L"type"] = new JSONValue(JSON::s2ws(v.type));
					watcher[L"timestampMode"] = new JSONValue(v.timestampMode);
					watchers.emplace_back(new JSONValue(watcher));
				}
				JSONObject watcher;
				watcher[L"watchers"] = new JSONValue(watchers);
				watcher[L"sampleRate"] = new JSONValue(float(sampleRate));
				watcher[L"timestamp"] = new JSONValue(double(timestamp));
				sendJsonResponse(new JSONValue(watcher), WSServer::kThreadCallback);
			} else
			if("watch" == cmd || "unwatch" == cmd || "control" == cmd || "uncontrol" == cmd || "log" == cmd || "unlog" == cmd || "monitor" == cmd) {
				const JSONArray& watchers = JSONGetArray(el, "watchers");
				const JSONArray& periods = JSONGetArray(el, "periods"); // used only by 'monitor'
				const JSONArray& timestamps = JSONGetArray(el, "timestamps"); // used only by some commands
				const JSONArray& durations = JSONGetArray(el, "durations"); // used only by some commands
				size_t numSent = 0;
				for(size_t n = 0; n < watchers.size(); ++n)
				{
					std::string str = JSONGetAsString(watchers[n]);
					Priv* p = findPrivByName(str);
#ifdef WATCHER_PRINT
					printf("%s {'%s', %p, ", cmd.c_str(), str.c_str(), p);
#endif // WATCHER_PRINT
					if(p)
					{
						AbsTimestamp timestamp = 0;
						AbsTimestamp duration = 0;
						MsgToRt msg {
							.priv = p,
							.cmd = MsgToRt::kCmdNone,
						};
						if(n < timestamps.size())
						{
							timestamp = JSONGetAsNumber(timestamps[n]);
#ifdef WATCHER_PRINT
							printf("timestamp: %llu, ", timestamp);
#endif // WATCHER_PRINT
						}
						if(n < durations.size())
						{
							duration = JSONGetAsNumber(durations[n]);
#ifdef WATCHER_PRINT
							printf("duration: %llu, ", duration);
#endif // WATCHER_PRINT
						}
						if("watch" == cmd) {
							msg.cmd = MsgToRt::kCmdStartWatching;
							msg.args[0] = timestamp;
							msg.args[1] = duration;
						} else if("unwatch" == cmd) {
							msg.cmd = MsgToRt::kCmdStopWatching;
							msg.args[0] = timestamp;
						}
						else if("control" == cmd)
							startControlling(p);
						else if("uncontrol" == cmd)
							stopControlling(p);
						else if("log" == cmd) {
							if(isStreaming(p, kStreamIdxLog))
								continue;
							msg.cmd = MsgToRt::kCmdStartLogging;
							msg.args[0] = timestamp;
							msg.args[1] = duration;
							setupLogger(p);
						} else if("unlog" == cmd) {
							msg.cmd = MsgToRt::kCmdStopLogging;
							msg.args[0] = timestamp;
						} else if ("monitor" == cmd) {
							if(n < periods.size())
							{
								size_t period = JSONGetAsNumber(periods[n]);
								setMonitoring(p, period);
							} else {
								fprintf(stderr, "monitor cmd with not enough elements in periods: %u instead of %u\n", periods.size(), watchers.size());
								break;
							}
						}
						if(MsgToRt::kCmdNone != msg.cmd)
						{
							pipe.writeNonRt(msg);
							numSent++;
						}
					}
#ifdef WATCHER_PRINT
					printf("}\n");
#endif // WATCHER_PRINT
				}
				if(numSent)
				{
					// this full memory barrier may be
					// unnecessary as the system calls in Pipe::writeRt()
					// may be enough
					// or it may be useless and still leave the problem unaddressed
					std::atomic_thread_fence(std::memory_order_release);
					pipeSentNonRt += numSent;
				}
			} else
			if("set" == cmd || "setMask" == cmd) {
				const JSONArray& watchers = JSONGetArray(el, "watchers");
				const JSONArray& values = JSONGetArray(el, "values");
				const JSONArray& masks = JSONGetArray(el, "masks");
				if(watchers.size() != values.size()) {
					fprintf(stderr, "set: incompatible size of watchers and values\n");
					return false;
				}
				for(size_t n = 0; n < watchers.size(); ++n)
				{
					std::string name = JSONGetAsString(watchers[n]);
					double val = JSONGetAsNumber(values[n]);
					Priv* p = findPrivByName(name);
					if(p)
					{
						if("set" == cmd)
							p->w->wmSet(val);
						else if("setMask" == cmd) {
							if(n > masks.size())
								break;
							unsigned int mask = JSONGetAsNumber(masks[n]);
							p->w->wmSetMask(val, mask);
						}
					}
				}
			} else
				printf("Unhandled command cmd: %s\n", cmd.c_str());
		}
		return false;
	}
	std::vector<Priv*> vec;
	float sampleRate = 0;
	Gui& gui;
	bool clientActive = true;
};

WatcherManager* Bela_getDefaultWatcherManager();

template <typename T>
class Watcher : public WatcherBase {
    static_assert(
	std::is_same<T,char>::value
	|| std::is_same<T,unsigned int>::value
	|| std::is_same<T,int>::value
	|| std::is_same<T,float>::value
	|| std::is_same<T,double>::value
	, "T is not of a supported type");
public:
	Watcher() = default;
	Watcher(const std::string& name, WatcherManager::TimestampMode timestampMode = WatcherManager::kTimestampBlock, WatcherManager* wm = Bela_getDefaultWatcherManager()) :
		wm(wm)
	{
		if(wm)
			d = wm->reg<T>(this, name, timestampMode);
	}
	virtual ~Watcher() {
		if(wm)
			wm->unreg(this);
	}
	operator T()
	{
		return get();
	}
	double wmGet() override
	{
		return get();
	}
	double wmGetInput() override {
		return v;
	}
	void wmSet(double value) override
	{
		vr = value;
	}
	// TODO: figure out how to provide  NOP alternative via enable_if for
	// non-integer types
	// template <typename = std::enable_if<std::is_integral<T>::value>>
	void wmSetMask(unsigned int value, unsigned int mask) override
	{
		this->mask = mask;
		vr = ((unsigned int)vr & ~mask) | (value & mask);
	}
	unsigned int getMask()
	{
		return this->mask;
	}
	// TODO: use template functions to cast to numerical types if T is numerical
	void operator=(T value) {
		set(value);
	}
	void set(const T& value) {
		v = value;
		if(wm)
			wm->notify(d, v);
	}
	void localControlChanged() override
	{
		// if disabling local control, initialise the remote value with
		// the current value
		if(!localControlEnabled)
			vr = v;
	}
	T get() {
		if(localControlEnabled)
			return v;
		else
			return vr;
	}
protected:
	T v {};
	T vr {};
	WatcherManager* wm;
	WatcherManager::Details* d;
	unsigned int mask;
};

