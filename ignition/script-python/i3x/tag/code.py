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
			quality = "GOOD"
			timestamp = alarmObj["eventTime"]
			value = {"value":alarmObj, "quality":quality, "timestamp":timestamp}
		else:
			value = i3x.ignition.getTagValue(self.udtInstance, tagChangeEvent.getValue())
		
		if value != None:
			newValue = {}
			newValue.update(value["value"])
			newValue["elementId"] = self.elementId
			newValue["sequenceNumber"] = self.subscription["sequenceNumber"]
			self.subscription["sequenceNumber"] += 1
			self.subscription["queuedUpdates"].append(newValue)
		
def subscribe(elementId, tagPathStr, udtInstance, subscription):
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	from com.inductiveautomation.ignition.common.tags.paths.parser import TagPathParser
	
	context = IgnitionGateway.get()
	tagManager = context.getTagManager()
	
	if udtInstance["typeId"] == "ignition-alarm":
		tagPathStr = i3x.utils.alarmSourceToStateTagPath(tagPathStr)

	tagPath = TagPathParser.parse(tagPathStr)
	listener = I3XTagChangeListener(elementId, tagPathStr, udtInstance, subscription)
	subscription["listeners"][elementId] = listener
	tagManager.subscribeAsync(tagPath, listener)
	
def unsubscribe(elementId, tagPathStr, udtInstance, subscription):
	from com.inductiveautomation.ignition.gateway import IgnitionGateway
	from com.inductiveautomation.ignition.common.tags.paths.parser import TagPathParser
	
	context = IgnitionGateway.get()
	tagManager = context.getTagManager()
	
	if udtInstance["typeId"] == "ignition-alarm":
		tagPathStr = i3x.utils.alarmSourceToStateTagPath(tagPathStr)

	tagPath = TagPathParser.parse(tagPathStr)
	tagManager.unsubscribeAsync(tagPath, subscription["listeners"][elementId])
	del subscription["listeners"][elementId]