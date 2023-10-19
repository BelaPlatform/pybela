// when running with old version of the core GUI, the type property of
// Bela.data.buffers[x] is not set in the backend. This flag is set at runtime
// if we detect the need for it and enables a workaround
let backwCompatibility = false;
let backwTypes = Array();

let controlsLeft = 10;
let controlsTop = 40;
let vSpace = 30;
let nameHspace = 80;
let hSpaces = [-nameHspace, 0, 40, 80, 130, 230, 340, 390, 490, 610, 690];
let sampleRateDiv;
let latestTimestampDiv;

function sendCommand(cmd) {
	Bela.control.send({
		watcher: Array.isArray(cmd) ? cmd : [ cmd ],
	});
}

function requestWatcherList() {
	sendCommand({cmd: "list"});
}

let watcherGuiUpdatingFromBackend = false;

function parseString(parent, value)
{
	// be lenient in parsing the string.
	// remove whitespaces
	value = value.trim();
	let out;
	let isHex = false;
	if(0 == value.search(/^0[xX]/)) {
		// if it starts with 0x, remove it (we will parse it as hex anyhow)
		value = value.replace(/^0[Xx]/, '');
		// now remove any separators you may have added for legibility
		value = value.replace(/[^0-9a-fA-F]/g,'');
		// and make it an actual hex if appropriate
		value = "0x" + value;
		out = parseInt(value);
		isHex = true;
	} else if(-1 == value.search(/\./)) {
		// no decimal separator, assume integer
		out = parseInt(value);
	} else {
		out = parseFloat(value);
	}
	parent.isHex = isHex;
	return out;
}

function formatNumber(parent, value)
{
	return (parent.isHex ? "0x" : "") + value.toString(parent.isHex ? 16 : 10);
}

document.addEventListener('visibilitychange', function() {
	updateClientActive(!document.hidden)
});

let clientActive = null;
function updateClientActive(active) {
	if(active !== clientActive) {
		clientActive = active;
		let evt = clientActive ? "active" : "inactive";
		Bela.control.send({event: evt});
	}
}
let masks = {};

// `this` is the object that has changed
function watcherControlSendToBela()
{
	if(watcherGuiUpdatingFromBackend)
		return;
	let value = this.value();
	if(this.checked) // checkboxes
		value = this.checked();
	if(this.parser)
		value = this.parser(value);
	else
		if(typeof(value) === "string")
			value = parseString(this.guiKey.parent, value);
	if(isNaN(value)) {
		// this is required for the C++ parser to recognize is it as a
		// number (NaN is not recognized as a number)
		value = 0;
	}
	let obj = {
		watchers: [this.guiKey.name],
		// cmd and other members added below as necessary
	}
	switch(this.guiKey.property)
	{
		case "watched":
			if(value) {
				obj.cmd = "watch";
				this.lastStartedWatching = performance.now();
			} else
				obj.cmd = "unwatch";
			break;
		case "controlled":
			if(value)
				obj.cmd = "control";
			else
				obj.cmd = "uncontrol";
			break;
		case "logged":
			if(value) {
				obj.cmd = "log";
				obj.timestamps = [ latestTimestamp + 2 * sampleRate ];
				// can also pass durations to stop at a scheduled time
				// obj.durations = [ 6 * sampleRate ];
			}
			else
				obj.cmd = "unlog";
			break;
		case "valueInput":
			obj.values = [value];
			let mask = masks[this.guiKey];
			if(mask) {
				obj.cmd = "setMask";
				obj.masks = [mask];
			} else
				obj.cmd = "set";
			break;
		case "maskInput":
			masks[this.guiKey] = value;
			// do not send
			return;
		case "monitorPeriod":
			obj.cmd = "monitor";
			obj.periods = [value];
			break;
		default:
			console.log("unhandled property", this.guiKey.property);
			// do not send
			return;
	}
	console.log("Sending ", obj);
	sendCommand(obj);
}

function watcherSenderInit(obj, guiKey, parser)
{
	if(!obj)
		return;
	obj.guiKey = guiKey;
	if("button" === obj.elt.localName)
		obj.mouseReleased(sendToBela);
	else
		obj.input(watcherControlSendToBela);
	obj.parser = parser;
	//watcherControlSendToBela.call(obj);
}

let wGuis = {};
function watcherUpdateLayout() {
	let i = 0;
	for(let k in wGuis) {
		let w = wGuis[k];
		let n = 0;
		for(let o in w) {
			if(w[o])
				w[o].position(controlsLeft + nameHspace + hSpaces[n], controlsTop + vSpace * i);
			n++;
		}
		i++;
	}
}
function addWatcherToList(watcher) {
	let hasMask = watcher.type != 'd' && watcher.type != 'f';
	let w = {
		nameDisplay: createElement("div", watcher.name),
		watched: createCheckbox("W", watcher.watched),
		controlled: createCheckbox("C", watcher.controlled),
		logged: createCheckbox("L", watcher.logged),
		valueInput: createInput(""),
		maskInput: hasMask ? createInput("") : undefined,
		valueType: createElement("div", watcher.type),
		valueDisplay: createElement("div", watcher.value),
		monitorPeriod: createInput("0"),
		monitorTimestamp: createElement("div", "_"),
		monitorValue: createElement("div", "_"),
	};
	w.valueInput.elt.style = "width: 13ch";
	if(hasMask)
		w.maskInput.elt.style = "width: 13ch";
	w.monitorPeriod.elt.style = "width: 13ch";
	w.monitorPeriod.elt.value = watcher.monitor;
	for(let i in w)
		watcherSenderInit(w[i], {name: watcher.name, property: i, parent: w});
	wGuis[watcher.name] = w;
	watcherUpdateLayout();
}

function removeWatcherFromList(watcher) {
	wGuis[watcher].watched.remove();
	wGuis[watcher].controlled.remove();
	wGuis[watcher].logged.remove();
	wGuis[watcher].valueInput.remove();
	wGuis[watcher].maskInput.remove();
	wGuis[watcher].valueType.remove();
	wGuis[watcher].valueDisplay.remove();
	wGuis[watcher].monitorPeriod.remove();
	wGuis[watcher].monitorTimestamp.remove();
	wGuis[watcher].monitorValue.remove();
	delete wGuis[watcher];
}

function updateWatcherGuis(w, n) {
	if(backwCompatibility)
	{
		backwTypes[n] = w.type;
	}
	// avoid sending message to backend while we are updating
	watcherGuiUpdatingFromBackend = true;
	let wgui = wGuis[w.name];
	wgui.watched.checked(w.watched);
	wgui.controlled.checked(w.controlled);
	wgui.logged.checked(w.logged);
	wgui.logged.elt.title = w.logFileName;
	wgui.valueType.elt.innerText = w.type;
	wgui.valueDisplay.elt.innerText = formatNumber(wgui, w.value);
	watcherGuiUpdatingFromBackend = false;
}

let latestTimestamp = 0;
let sampleRate = 0;
function updateWatcherList(data) {
	setTimeout(requestWatcherList, 1234); // request a new one
	latestTimestamp = data.timestamp;
	sampleRate = data.sampleRate;
	sampleRateDiv.elt.innerText = sampleRate + "Hz";
	latestTimestampDiv.elt.innerText = latestTimestamp;
	let newList = data.watchers;
	for(let n = 0; n < newList.length; ++n) {
		if(!(newList[n].name in wGuis)) {
			addWatcherToList(newList[n]);
		}
		updateWatcherGuis(newList[n], n);
	}
	for(let i in wGuis) {
		let found = false;
		for(let n = 0; n < newList.length; ++n) {
			if(i == newList[n].name) {
				found = true;
				break;
			}
		}
		if(!found)
			removeWatcherFromList(i);
	}
}

let controlCallback = (data) => {
	if(data.watcher && data.watcher.watchers)
		updateWatcherList(data.watcher);
	else
		console.log(data.watcher);
}

function setup() {
	//Create a canvas of dimensions given by current browser window
	createCanvas(windowWidth, windowHeight);

	//text font
	textFont('Courier New');
	requestWatcherList();
	Bela.control.registerCallback("controlCallback", controlCallback, { val: 1, otherval: 2});
	let top = controlsTop - 40;
	createElement("div", "control<br>value").position(controlsLeft + nameHspace + hSpaces[4], top);
	createElement("div", "control<br>mask").position(controlsLeft + nameHspace + hSpaces[5], top);
	createElement("div", "type").position(controlsLeft + nameHspace + hSpaces[6], top);
	createElement("div", "list<br>value").position(controlsLeft + nameHspace + hSpaces[7], top);
	createElement("div", "monitor<br>interval").position(controlsLeft + nameHspace + hSpaces[8], top);
	createElement("div", "monitor<br>timestamp").position(controlsLeft + nameHspace + hSpaces[9], top);
	createElement("div", "monitor<br>value").position(controlsLeft + nameHspace + hSpaces[10], top);
	sampleRateDiv = createElement("div", "").position(controlsLeft, top);
	latestTimestampDiv = createElement("div", "").position(controlsLeft + 100, top);
}

let pastBuffer;
let clientActiveTimeout;
function draw() {
	//Read buffer with index 0 coming from render.cpp.
	let p = this;
	var buffers = Bela.data.buffers;
	if(!buffers.length)
		return;

	p.background(255)

	p.strokeWeight(1);
	var linVerScale = 1;
	var linVerOff = 0;
	let keys = Object.keys(wGuis);
	for(let k in buffers)
	{
		let timestampBuf;
		let type = buffers[k].type;
		if(!type) {
			// when running with old version of the core GUI, type has to be set elsewhere
			backwCompatibility = true;
			type = backwTypes[k];
		}
		let buf;
		switch(type)
		{
			case 'c':
				// absurb reverse mapping of an absurd fwd mapping
				let intArr = buffers[k].slice(0, 8).map((e) => {
					return e.charCodeAt(0);
				});
				timestampBuf = new Uint8Array(intArr);
				buf = buffers[k].slice(8);
				break;
			case 'j': // unsigned int
				timestampBuf = new Uint32Array(buffers[k].slice(0, 2))
				buf = buffers[k].slice(2);
				break;
			case 'i': // int
				timestampBuf = new Int32Array(buffers[k].slice(0, 2))
				buf = buffers[k].slice(2);
				break;
			case 'f': // float
				timestampBuf = new Float32Array(buffers[k].slice(0, 2));
				buf = buffers[k].slice(2);
				break;
			case 'd':
				timestampBuf = new Float64Array(buffers[k].slice(0, 1));
				buf = buffers[k].slice(1);
				break;
			default:
				console.log("Unknown buffer type ", type);
				continue;
		}
		let timestampUint32 = new Uint32Array(timestampBuf.buffer);
		let timestamp = timestampUint32[0] * (1 << 32) + timestampUint32[1];
		if(1 == buf.length) {
			// "monitoring" message
			let w = wGuis[keys[k]];
			w.monitorTimestamp.elt.innerText = timestamp;
			w.monitorValue.elt.innerText = formatNumber(w, buf[0]);
			continue;
		}
		let obj = wGuis[keys[k]].watched;
		let bts = buffers[k].ts;
		let now = performance.now();
		// early return if the buffer has not been update since last set to watch
		// or if the last update is too old
		if(bts < obj.lastStartedWatching || now - 2000 > bts)
			continue;
		// fade out as it gets old
		let alpha = 1 - (now - 1000 - bts) / 1000;
		alpha *= 255; // effectively clipped to 255 by color()
		if(alpha < 0)
			alpha = 0;
		p.noFill();
		var rem = k % 3;
		p.stroke(p.color(255 * (0 == rem), 255 * (1 == rem), 255 * (2 == rem), alpha));
		p.beginShape();
		for (let i = 0; i < buf.length; i++) {
			var y;
			y = buf[i] * linVerScale + linVerOff;
			x = i / (buf.length - 1);
			p.vertex(p.windowWidth * x, p.windowHeight * (1 - y));
		}
		p.endShape();
	}
}

function windowResized() {
	watcherUpdateLayout();
	resizeCanvas(windowWidth, windowHeight);
}
