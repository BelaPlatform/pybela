#include <vector>
#include <typeinfo>
#include <string>
#include <new> // for std::bad_alloc
#include <unistd.h>

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
	virtual void wmSet(double) = 0;
	virtual void localControlChanged() {}
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

class WatcherManager
{
	static constexpr uint32_t kMonitorDont = 0;
	static constexpr uint32_t kMonitorChange = 1 << 31;
	typedef uint64_t AbsTimestamp;
	typedef uint32_t RelTimestamp;
	AbsTimestamp timestamp = 0;
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
	WatcherManager(Gui& gui) : gui(gui) {
		gui.setControlDataCallback([this](JSONObject& json, void*) {
			this->controlCallback(json);
			return true;
		});
	};
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
			.type = typeid(T).name(),
			.timestampMode = timestampMode,
			.firstTimestamp = 0,
			.relTimestampsOffset = getRelTimestampsOffset(sizeof(T)),
			.countRelTimestamps = 0,
			.monitoring = kMonitorDont,
			.watched = false,
			.controlled = false,
			.logged = kLoggedNo,
			.hasLogged = false,
		});
		Priv* p = vec.back();
		p->v.resize(kBufSize); // how do we include this above?
		if(((uintptr_t)p->v.data() + kMsgHeaderLength) & (sizeof(T) - 1))
			throw(std::bad_alloc());
		p->maxCount = kTimestampBlock == p->timestampMode ? p->v.size() : p->relTimestampsOffset - (sizeof(T) - 1);
		setupLogger(p);
		return (Details*)vec.back();
	}
	void unreg(WatcherBase* that)
	{
		auto it = std::find_if(vec.begin(), vec.end(), [that](decltype(vec[0])& item){
			return item->w == that;
		});
		bool shouldDiscard = !(*it)->hasLogged;
		(*it)->logger->cleanup(shouldDiscard);
		delete (*it)->logger;
		// TODO: unregister from GUI
		delete *it;
		vec.erase(it);
	}
	void tick(AbsTimestamp frames)
	{
		timestamp = frames;
	}
	// the relevant object is passed back here so that we don't have to waste
	// time looking it up
	template <typename T>
	void notify(Details* d, const T& value)
	{
		Priv* p = reinterpret_cast<Priv*>(d);
		if(!p)
			return;
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
				// big enough for the timestamp and one value
				// and possibly some padding bytes at the end
				// (though in practice there won't be any when
				// sizeof(T) <= kMsgHeaderLength)
				uint8_t data[((kMsgHeaderLength + sizeof(value) + sizeof(T) - 1) / sizeof(T)) * sizeof(T)];
				memcpy(data, &timestamp, kMsgHeaderLength);
				memcpy(data + kMsgHeaderLength, &value, sizeof(value));
				gui.sendBuffer(p->guiBufferId, (T*)data, sizeof(data) / sizeof(T));
				if(1 == p->monitoring)
				{
					// special case: one-shot
					// so disable at the next iteration
					p->monitoring = kMonitorChange | 0;
				} else
					p->monitoringNext = timestamp + p->monitoring;
			}
		}
		if(p->watched || kLoggedNo != p->logged)
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
			if(full || kLoggedStopping == p->logged)
			{
				if(kLoggedStopping == p->logged && !full)
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
				if(kLoggedStopping == p->logged)
				{
					p->logger->requestFlush();
					p->logged = kLoggedNo;
				}
				p->count = 0;
			}
		}
	}
private:
	enum Logged {
		kLoggedNo,
		kLoggedYes,
		kLoggedStopping,
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
		uint64_t monitoringNext;
		bool watched;
		bool controlled;
		Logged logged;
		bool hasLogged;
	};
	template <typename T>
	void send(Priv* p) {
		size_t size = p->v.size(); // TODO: customise this for smaller frames
		if(p->watched)
			gui.sendBuffer(p->guiBufferId, (T*)p->v.data(), size / sizeof(T));
		if((p->logged != kLoggedNo) && p->logger)
			p->logger->log((float*)p->v.data(), size / sizeof(float));
	}
	void startWatching(Priv* p) {
		if(p->watched)
			return;
		p->watched = true;
		p->count = 0;
		// TODO: register guiBufferId here
	}
	void stopWatching(Priv* p) {
		if(!p->watched)
			return;
		p->watched = false;
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
	void startLogging(Priv* p) {
		if(kLoggedNo != p->logged)
			return;
		p->logged = kLoggedYes;
		p->hasLogged = true;
	}
	void stopLogging(Priv* p) {
		if(kLoggedNo == p->logged)
			return;
		p->logged = kLoggedStopping;
	}
	void setMonitoring(Priv* p, size_t period) {
		p->monitoring = (kMonitorChange | period);
	}
	void setupLogger(Priv* p) {
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

	Priv* findPrivByName(const std::string& str) {
		auto it = std::find_if(vec.begin(), vec.end(), [&str](decltype(vec[0])& item) {
			return item->name == str;
		});
		if(it != vec.end())
			return *it;
		else
			return nullptr;
	}
	bool controlCallback(JSONObject& root) {
		auto watcher = JSONGetArray(root, "watcher");
		for(size_t n = 0; n < watcher.size(); ++n)
		{
			JSONValue* el = watcher[n];
			std::string cmd = JSONGetString(el, "cmd");
			printf("Command cmd: %s\n\r", cmd.c_str());
			if("list" == cmd)
			{
				// send watcher list JSON
				JSONArray watchers;
				for(auto& item : vec)
				{
					auto& v = *item;
					JSONObject watcher;
					watcher[L"name"] = new JSONValue(JSON::s2ws(v.name));
					watcher[L"watched"] = new JSONValue(v.watched);
					watcher[L"controlled"] = new JSONValue(v.controlled);
					watcher[L"logged"] = new JSONValue(v.logged);
					watcher[L"monitor"] = new JSONValue(int((~kMonitorChange) & v.monitoring));
					watcher[L"logFileName"] = new JSONValue(JSON::s2ws(v.logFileName));
					watcher[L"value"] = new JSONValue(v.w->wmGet());
					watcher[L"type"] = new JSONValue(JSON::s2ws(v.type));
					watcher[L"timestampMode"] = new JSONValue(v.timestampMode);
					watchers.emplace_back(new JSONValue(watcher));
				}
				JSONObject watcher;
				watcher[L"watchers"] = new JSONValue(watchers);
				JSONObject root;
				root[L"watcher"] = new JSONValue(watcher);
				JSONValue value(root);
				gui.sendControl(&value, WSServer::kThreadCallback);
			}
			if("watch" == cmd || "unwatch" == cmd || "control" == cmd || "uncontrol" == cmd || "log" == cmd || "unlog" == cmd || "monitor" == cmd) {
				const JSONArray& watchers = JSONGetArray(el, "watchers");
				for(size_t n = 0; n < watchers.size(); ++n)
				{
					std::string str = JSONGetAsString(watchers[n]);
					Priv* p = findPrivByName(str);
					printf("%s {'%s', %p}, ", cmd.c_str(), str.c_str(), p);
					if(p)
					{
						if("watch" == cmd)
							startWatching(p);
						else if("unwatch" == cmd)
							stopWatching(p);
						else if("control" == cmd)
							startControlling(p);
						else if("uncontrol" == cmd)
							stopControlling(p);
						else if("log" == cmd)
							startLogging(p);
						else if("unlog" == cmd)
							stopLogging(p);
						else if ("monitor" == cmd) {
							const JSONArray& periods = JSONGetArray(el, "periods");
							size_t period = JSONGetAsNumber(periods[n]);
							setMonitoring(p, period);
						}
					}
				}
				printf("\n");
			}
			if("set" == cmd) {
				const JSONArray& watchers = JSONGetArray(el, "watchers");
				const JSONArray& values = JSONGetArray(el, "values");
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
						p->w->wmSet(val);
					}
				}
			}
		}
		return false;
	}
	std::vector<Priv*> vec;
	Gui& gui;
};

Gui gui;
WatcherManager* Bela_getDefaultWatcherManager()
{
	static WatcherManager defaultWatcherManager(gui);
	return &defaultWatcherManager;
}

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
	~Watcher() {
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
	void wmSet(double value) override
	{
		vr = value;
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
	T vr;
	WatcherManager* wm;
	WatcherManager::Details* d;
};

