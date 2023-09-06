function sendCommand(cmd) {
	Bela.control.send({
		watcher: Array.isArray(cmd) ? cmd : [ cmd ],
	});
}

function requestWatcherList() {
	sendCommand({cmd: "list"});
}

let watcherGuiUpdatingFromBackend = false;

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
			value = parseFloat(value);
	if(isNaN(value)) {
		// this is required for the C++ parser to recognize is it as a
		// number (NaN is not recognized as a number)
		value = 0;
	}
	this.guiKey.name;
	let obj = {
		watchers: [this.guiKey.name],
		// cmd and other members added below as necessary
	}
	switch(this.guiKey.property)
	{
		case "watched":
			if(value)
				obj.cmd = "watch";
			else
				obj.cmd = "unwatch";
			break;
		case "controlled":
			if(value)
				obj.cmd = "control";
			else
				obj.cmd = "uncontrol";
			break;
		case "logged":
			if(value)
				obj.cmd = "log";
			else
				obj.cmd = "unlog";
			break;
		case "valueInput":
			obj.cmd = "set";
			obj.values = [value];
			break;
	}
	console.log("Sending ", obj);
	sendCommand(obj);
}

function watcherSenderInit(obj, guiKey, parser)
{
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
	let controlsLeft = 10;
	let controlsTop = 10;
	let vSpace = 30;
	let nameHspace = 80;
	let hSpaces = [-nameHspace, 0, 40, 80, 130, 280, 300 ];
	let i = 0;
	for(let k in wGuis) {
		let w = wGuis[k];
		let n = 0;
		for(let o in w) {
			w[o].position(controlsLeft + nameHspace + hSpaces[n], controlsTop + vSpace * i);
			n++;
		}
		i++;
	}
}
function addWatcherToList(watcher) {
	let w = {
		nameDisplay: createElement("div", watcher.name),
		watched: createCheckbox("W", watcher.watched),
		controlled: createCheckbox("C", watcher.controlled),
		logged: createCheckbox("L", watcher.logged),
		valueInput: createInput(""),
		valueType: createElement("div", watcher.type),
		valueDisplay: createElement("div", watcher.value),
	};
	for(let i in w)
		watcherSenderInit(w[i], {name: watcher.name, property: i});
	wGuis[watcher.name] = w;
	watcherUpdateLayout();
}

function removeWatcherFromList(watcher) {
	wGuis[watcher].watched.remove();
	wGuis[watcher].controlled.remove();
	wGuis[watcher].logged.remove();
	wGuis[watcher].valueInput.remove();
	wGuis[watcher].valueType.remove();
	wGuis[watcher].valueDisplay.remove();
	delete wGuis[watcher];
}

function updateWatcherGuis(w) {
	// avoid sending message to backend while we are updating
	watcherGuiUpdatingFromBackend = true;
	let wgui = wGuis[w.name];
	wgui.watched.checked(w.watched);
	wgui.controlled.checked(w.controlled);
	wgui.logged.checked(w.logged);
	wgui.logged.elt.title = w.logFileName;
	wgui.valueType.elt.innerText = w.type;
	wgui.valueDisplay.elt.innerText = w.value;
	watcherGuiUpdatingFromBackend = false;
}

function updateWatcherList(newList) {
	console.log(newList);
	for(let n = 0; n < newList.length; ++n) {
		if(!(newList[n].name in wGuis)) {
			addWatcherToList(newList[n]);
		}
		updateWatcherGuis(newList[n]);
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
	if(data.watcher.watchers)
		updateWatcherList(data.watcher.watchers);
}

function setup() {
	//Create a canvas of dimensions given by current browser window
	createCanvas(windowWidth, windowHeight);

	//text font
	textFont('Courier New');
	requestWatcherList();
	Bela.control.registerCallback("controlCallback", controlCallback, { val: 1, otherval: 2});
}
setInterval(requestWatcherList, 500);

let pastBuffer;
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
		if(!wGuis[keys[k]].watched.checked())
			continue;
		let timestampBuf;
		let type = Bela.data.buffers[k].type;
		switch(type)
		{
			case 'c':
				// absurb reverse mapping of an absurd fwd mapping
				let intArr = buffers[k].slice(0, 8).map((e) => {
					return e.charCodeAt(0);
				});
				timestampBuf = new Uint8Array(intArr);
				break;
			case 'j': // unsigned int
				timestampBuf = new Uint32Array(buffers[k].slice(0, 2))
				break;
			case 'i': // int
				timestampBuf = new Int32Array(buffers[k].slice(0, 2))
				break;
			case 'f': // float
				timestampBuf = new Float32Array(buffers[k].slice(0, 2));
				break;
			case 'd':
				timestampBuf = new Float64Array(buffers[k].slice(0, 1));
				break;
			default:
				console.log("Unknown buffer type ", type);
		}
		let timestampUint32 = new Uint32Array(timestampBuf.buffer);
		let timestamp = timestampUint32[0] * (1 << 32) + timestampUint32[1];
		p.noFill();
		var rem = k % 3;
		p.stroke(p.color(255 * (0 == rem), 255 * (1 == rem), 255 * (2 == rem)));
		p.beginShape();
		let buf = buffers[k];
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
