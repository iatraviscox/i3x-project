from com.inductiveautomation.ignition.common.tags.model.event import TagChangeListener

MAX_QUEUE_SIZE = 1000

class I3XTagChangeListener(TagChangeListener):
	def __init__(self, elementId, tagPath, udtInstance, subscription):
		self.tagPath = tagPath
		self.elementId = elementId
		self.udtInstance = udtInstance
		self.subscription = subscription

	def tagChanged(self, tagChangeEvent):
		if self.udtInstance["typeId"] == "ignition-alarm":
			alarmObj = i3x.ignition.getAlarmFromSource(self.udtInstance["path"])["alarmObj"]
			entry = {"value":alarmObj, "quality":"Good", "timestamp":alarmObj["eventTime"]}
		else:
			value = i3x.ignition.getTagValue(self.udtInstance, tagChangeEvent.getValue())
			if value is None:
				return
			vqt = value["value"]
			entry = {"value":vqt["value"], "quality":vqt["quality"], "timestamp":vqt["timestamp"]}

		# SyncUpdateEntry shape: {elementId, value, quality, timestamp}
		update = {"elementId":self.elementId}
		update.update(entry)

		# Stage the update for the next sync(). Mutated from tag threads while
		# sync() reads from web threads, so guard with the subscription lock.
		lock = self.subscription["lock"]
		with lock:
			staged = self.subscription["stagedUpdates"]
			wasFull = staged.maxlen is not None and len(staged) == staged.maxlen
			staged.append(update)
			if wasFull:
				self.subscription["overflow"] = True

def subscribe(elementId, tagPathStr, udtInstance, subscription):
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	from com.inductiveautomation.ignition.common.tags.paths.parser import TagPathParser

	context = IgnitionGateway.get()
	tagManager = context.getTagManager()

	if udtInstance["typeId"] == "ignition-alarm":
		tagPathStr = i3x.utils.alarmSourceToStateTagPath(tagPathStr)

	tagPath = TagPathParser.parse(tagPathStr)
	listener = I3XTagChangeListener(elementId, tagPathStr, udtInstance, subscription)
	tagManager.subscribeAsync(tagPath, listener)
	return listener

def unsubscribe(tagPathStr, udtInstance, listener):
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	from com.inductiveautomation.ignition.common.tags.paths.parser import TagPathParser

	context = IgnitionGateway.get()
	tagManager = context.getTagManager()

	if udtInstance["typeId"] == "ignition-alarm":
		tagPathStr = i3x.utils.alarmSourceToStateTagPath(tagPathStr)

	tagPath = TagPathParser.parse(tagPathStr)
	tagManager.unsubscribeAsync(tagPath, listener)
