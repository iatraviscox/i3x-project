SPEC_VERSION = "1.0"

def handleResponse(request, errorCode, isBulk, bulkError, error, result):
	resp = request["servletResponse"]
	resp.setStatus(errorCode)

	# 2xx (200 OK, 206 Partial Content) carry the success/result envelope.
	if 200 <= errorCode < 300:
		ret = {
			"success": not bulkError,
			"results" if isBulk else "result": result
		}
		return {'json': system.util.jsonEncode(ret)}

	# Everything else uses the spec ErrorResponse {success:false, responseDetail}.
	ret = {
		"success": False,
		"responseDetail": i3x.utils.errorDetail(errorCode, error)
	}
	return {'json': system.util.jsonEncode(ret)}

def serverError(loggerName):
	# Log the full traceback server-side; never leak internals to the client.
	import traceback
	system.util.getLogger(loggerName).error(traceback.format_exc())
	return (500, False, "Internal server error", None)

def bulkOk(result, elementId=None, subscriptionId=None):
	item = {"success": True, "result": result}
	if elementId is not None:
		item["elementId"] = elementId
	if subscriptionId is not None:
		item["subscriptionId"] = subscriptionId
	return item

def bulkErr(status, detail, elementId=None, subscriptionId=None):
	item = {"success": False, "result": None, "responseDetail": i3x.utils.errorDetail(status, detail)}
	if elementId is not None:
		item["elementId"] = elementId
	if subscriptionId is not None:
		item["subscriptionId"] = subscriptionId
	return item

def getInfo():
	ret = {
		"specVersion": SPEC_VERSION,
		"serverVersion": system.util.getVersion().toString(),
		"serverName": system.tag.readBlocking(["[System]Gateway/SystemName"])[0].value,
		"capabilities": {
			"query": {
				"history": True
			},
			"update": {
				"current": False,
				"history": False
			},
			"subscribe": {
				"stream": False
			}
		}
	}	
	return (200, False, None, ret)

def getRelationshipTypes(namespaceUri=None, elementIds=None):
	log = system.util.getLogger("i3x.relationshiptypes")

	ret = []
	bulkError = False
	
	relationships = {
		"HasParent":{
			"elementId": "HasParent",
			"relationshipId": "HasParent",
			"displayName": "HasParent",
			"namespaceUri": "https://cesmii.org/i3x",
			"reverseOf": "HasChildren"
		},
		"HasChildren":{
			"elementId": "HasChildren",
			"relationshipId": "HasChildren",
			"displayName": "HasChildren",
			"namespaceUri": "https://cesmii.org/i3x",
			"reverseOf": "HasParent"
		},
		"HasComponent":{
			"elementId": "HasComponent",
			"relationshipId": "HasComponent",
			"displayName": "HasComponent",
			"namespaceUri": "https://cesmii.org/i3x",
			"reverseOf": "ComponentOf"
		},
		"ComponentOf":{
			"elementId": "ComponentOf",
			"relationshipId": "ComponentOf",
			"displayName": "ComponentOf",
			"namespaceUri": "https://cesmii.org/i3x",
			"reverseOf": "HasComponent"
		},
		"InheritedBy":{
			"elementId": "InheritedBy",
			"relationshipId": "InheritedBy",
			"displayName": "InheritedBy",
			"namespaceUri": "https://cesmii.org/i3x",
			"reverseOf": "InheritsFrom"
		},
		"InheritsFrom":{
			"elementId": "InheritsFrom",
			"relationshipId": "InheritsFrom",
			"displayName": "InheritsFrom",
			"namespaceUri": "https://cesmii.org/i3x",
			"reverseOf": "InheritedBy"
		},
		"HasAlarm":{
			"elementId": "HasAlarm",
			"relationshipId": "HasAlarm",
			"displayName": "HasAlarm",
			"namespaceUri": i3x.ignition.IgnitionNamespaceUri,
			"reverseOf": "AlarmOf"
		},
		"AlarmOf":{
			"elementId": "AlarmOf",
			"relationshipId": "AlarmOf",
			"displayName": "AlarmOf",
			"namespaceUri": i3x.ignition.IgnitionNamespaceUri,
			"reverseOf": "HasAlarm"
		}
	}
	
	if elementIds == None:
		for relationship in relationships:
			obj = relationships[relationship]
			dtNamespaceUri = relationships[relationship]["namespaceUri"]
			if namespaceUri == None or namespaceUri == dtNamespaceUri:
				ret.append(obj)
	else:
		for elementId in elementIds:
			if elementId != None:
				if elementId in relationships:
					ret.append(bulkOk(relationships[elementId], elementId=elementId))
				else:
					bulkError = True
					ret.append(bulkErr(404, "Relationship type not found: %s" % elementId, elementId=elementId))
		
	return (200, bulkError, None, ret)
	
def getNamespaces():
	import urlparse
	
	log = system.util.getLogger("i3x.namespaces")
	
	ret = []
	namespaces = []

	tagProviders = i3x.ignition.getTagProviders()
	
	for tagProvider in tagProviders:
		for row in i3x.ignition.getUdtDefs(tagProvider):
			dtNamespaceUri = i3x.utils.getNamespaceUriParam(row)
			if dtNamespaceUri not in namespaces:
				namespaces.append(dtNamespaceUri)
	
	coreUAFound = False
	for namespaceUri in namespaces:
		prefix = ""
		if namespaceUri.startswith("https://inductiveautomation.com/"):
			prefix = "Ignition "
			
		if namespaceUri == i3x.ignition.UaCoreUri:
			coreUAFound = True
			
		ret.append({"uri":namespaceUri, "displayName":prefix+" ".join([word.capitalize() if word.islower() else word for word in urlparse.urlparse(namespaceUri).path[1:].replace("/", " ").split()])})
	
	if not coreUAFound:
		ret.append({"uri":i3x.ignition.UaCoreUri, "displayName":"UA"})
	
	return (200, False, None, ret)

def getObjectTypes(namespaceUri=None, elementIds=None):
	log = system.util.getLogger("i3x.objecttypes")
	
	bulkError = False
	
	folderObj = {"elementId":"folder-type", "displayName":"Folder", "namespaceUri":i3x.ignition.UaCoreUri, "sourceTypeId":"folder-type", "version":"1.0.0", "schema":{"type":"object", "description":"Represents a folder", "related":{"relationshipType":"HasChildren"}}}
	tagProviderObj = {"elementId":"ignition-tag-provider", "displayName":"Tag Provider", "namespaceUri":i3x.ignition.IgnitionNamespaceUri, "sourceTypeId":"ignition-tag-provider", "version":"1.0.0", "schema":{"type":"object", "description":"Represents an Ignition tag provider", "related":{"relationshipType":"HasChildren"}}}
	alarmObj = {"elementId":"ignition-alarm", "displayName":"Alarm", "namespaceUri":i3x.ignition.IgnitionNamespaceUri, "sourceTypeId":"ignition-alarm", "version":"1.0.0", "schema":{"type":"object", "description":"Represents an Ignition alarm", "related":{"relationshipType":"AlarmOf"}, "properties":{
		"source": {
			"type": "string"
		},
		"name": {
			"type": "string"
		},
		"eventId": {
			"type": "string"
		},
		"displayPath": {
			"type": "string"
		},
		"count": {
			"type": "integer"
		},
		"label": {
			"type": "string"
		},
		"lastEventState": {
			"type": "string"
		},
		"notes": {
			"type": "string"
		},
		"priority": {
			"type": "string"
		},
		"state": {
			"type": "string"
		},
		"isActive": {
			"type": "boolean"
		},
		"isAcked": {
			"type": "boolean"
		},
		"isCleared": {
			"type": "boolean"
		},
		"isShelved": {
			"type": "boolean"
		},
		"activeData": {
			"type": "object"
		},
		"clearedData": {
			"type": "object"
		},
		"ackData": {
			"type": "object"
		}
	}}}

	tagProviders = i3x.ignition.getTagProviders()
	
	if elementIds != None:
		isBulk = True
		ret = []
		if "folder-type" in elementIds:
			ret.append(folderObj)
		if "ignition-tag-provider" in elementIds:
			ret.append(tagProviderObj)
		if "ignition-alarm" in elementIds:
			ret.append(alarmObj)
	else:
		isBulk = False
		elementIds = [None]
		ret = []
		if namespaceUri == None or namespaceUri == i3x.ignition.UaCoreUri:
			ret.append(folderObj)	
		
		if namespaceUri == None or namespaceUri == i3x.ignition.IgnitionNamespaceUri:
			ret.append(tagProviderObj)
		
		if namespaceUri == None or namespaceUri == i3x.ignition.IgnitionNamespaceUri:
			ret.append(alarmObj)
	
	for elementId in elementIds:
		foundElementId = False
		udtDef = None
		udtDefTagProvider = None
		if elementId != None:
			if elementId in ["folder-type", "ignition-tag-provider", "ignition-alarm"]:
				continue
				
			udtDef = i3x.utils.elementIdToPath(elementId)
			udtDefTagProvider = i3x.utils.getTagProviderFromPath(udtDef)
		
		for tagProvider in tagProviders:
			if udtDefTagProvider != None and tagProvider != udtDefTagProvider:
				continue
			
			res = i3x.ignition.getUdtDefs(tagProvider, udtDef)
			for row in res:
				dtNamespaceUri = i3x.utils.getNamespaceUriParam(row)
				dtElementId = i3x.utils.pathToElementId(str(row["fullPath"]))
				
				if namespaceUri == None or namespaceUri == dtNamespaceUri:
					if dtElementId == elementId:
						foundElementId = True
						
					obj = {"elementId":dtElementId, "displayName":row["name"], "namespaceUri":dtNamespaceUri, "sourceTypeId":dtElementId, "version": "1.0.0", "schema":i3x.ignition.buildSchema(row, tagProvider, dtNamespaceUri)}
					
					if isBulk:
						ret.append(bulkOk(obj, elementId=elementId))
					else:
						ret.append(obj)

		if isBulk and not foundElementId:
			bulkError = True
			ret.append(bulkErr(404, "Object type not found: %s" % elementId, elementId=elementId))
	
	return (200, bulkError, None, ret)
	
def getObjects(typeId=None, includeMetadata=False, root=None, elementIds=None, callType="list", relationshipType=None, maxDepth=1, startTime=None, endTime=None):
	log = system.util.getLogger("i3x.objects")
	
	bulkError = False
		
	if typeId != None:
		typeId = i3x.utils.elementIdToPath(typeId)

	udtInstances = i3x.ignition.getUdtInstances()
	
	isBulk = elementIds != None
	ret = []
		
	if not isBulk:
		for udtInstancePath in udtInstances:
			udtInstance = udtInstances[udtInstancePath]
			dtElementId = udtInstance["elementId"]
			dtTypeId = udtInstance["typeId"]
			
			if typeId == None or typeId == dtTypeId:
				if udtInstance["type"] == "folder" and udtInstance["parentUdt"] != None:
					continue
				
				if root and udtInstance["parentId"] != None:
					continue
					
				obj = i3x.utils.buildUdtInstanceObj(udtInstance, includeMetadata)
				ret.append(obj)
	else:
		for elementId in elementIds:
			found = False
		
			for udtInstancePath in udtInstances:
				udtInstance = udtInstances[udtInstancePath]
				dtElementId = udtInstance["elementId"]
				
				if udtInstance["type"] == "folder" and udtInstance["parentUdt"] != None:
					continue
				
				if elementId == dtElementId:
					found = True
					obj = i3x.utils.buildUdtInstanceObj(udtInstance, includeMetadata)
					
					if callType == "related":
						retObj = []
						retObj.extend(i3x.utils.getRelatedObjects(relationshipType, "HasParent", udtInstance, udtInstances, includeMetadata))
						retObj.extend(i3x.utils.getRelatedObjects(relationshipType, "AlarmOf", udtInstance, udtInstances, includeMetadata))
						retObj.extend(i3x.utils.getRelatedObjects(relationshipType, "ComponentOf", udtInstance, udtInstances, includeMetadata))
						retObj.extend(i3x.utils.getRelatedObjects(relationshipType, "HasChildren", udtInstance, udtInstances, includeMetadata))
						retObj.extend(i3x.utils.getRelatedObjects(relationshipType, "HasComponent", udtInstance, udtInstances, includeMetadata))
						retObj.extend(i3x.utils.getRelatedObjects(relationshipType, "HasAlarm", udtInstance, udtInstances, includeMetadata))
						
						ret.append(bulkOk(retObj, elementId=elementId))
					elif callType == "value":
						# value/quality/timestamp are required by CurrentValueResult;
						# folders and providers have no value, so default to GoodNoData.
						elementObj = {"value":None, "quality":"GoodNoData", "timestamp":i3x.utils.formatUtc(system.date.now()), "isComposition":udtInstance["isComposition"]}
						childrenValues = {}
						quality = None
						timestamp = None

						if udtInstance["typeId"] == "ignition-alarm":
							alarmObj = udtInstance["alarmObj"]
							quality = "Good"
							timestamp = alarmObj["eventTime"]
							elementObj = {"value":udtInstance["alarmObj"], "quality":quality, "timestamp":timestamp, "isComposition":False}
						elif udtInstance["typeId"] != "folder-type" and udtInstance["typeId"] != "ignition-tag-provider":
							value = system.tag.readBlocking([udtInstancePath])[0]
							value = i3x.ignition.getTagValue(udtInstance, value)
							if value != None:
								elementObj.update(value["value"])
								childrenValues = value["childrenValues"]
								quality = value["value"]["quality"]
								timestamp = value["value"]["timestamp"]

							i3x.utils.addChildrenValues(udtInstances, udtInstance, elementObj, childrenValues, quality, timestamp, 2, maxDepth)

						ret.append(bulkOk(elementObj, elementId=elementId))
					elif callType == "history":
						elementObj = {"values":[], "isComposition":udtInstance["isComposition"]}

						if udtInstance["typeId"] == "ignition-alarm":
							startTime = i3x.utils.parseUtc(startTime)
							endTime = i3x.utils.parseUtc(endTime)
							res = system.alarm.queryJournal(startTime, endTime, journalName="Journal", source=udtInstancePath)
							for row in res:
								alarmObj = i3x.ignition.getAlarmObj(row)
								elementObj["values"].append({"value":alarmObj, "quality":"Good", "timestamp":alarmObj["eventTime"], "isComposition":False})
						elif udtInstance["typeId"] != "folder-type" and udtInstance["typeId"] != "ignition-tag-provider":
							startTime = i3x.utils.parseUtc(startTime)
							endTime = i3x.utils.parseUtc(endTime)
							children = i3x.utils.getChildrenObjectNames(udtInstance, "HasComponent")
							tagConfig = system.tag.getConfiguration(udtInstancePath, True)
							if len(tagConfig) and "tags" in tagConfig[0]:
								objs = {"tags":[], "objects":{}}
								tags = i3x.utils.getTags(udtInstancePath, objs, tagConfig[0]["tags"], 1, maxDepth)
								if len(tags):
									minutes = system.date.minutesBetween(startTime, endTime)
									res = system.historian.queryAggregatedPoints(paths=tags, startTime=startTime, endTime=endTime, aggregates=["LastValue"] * len(tags), fillModes=["PREV"] * len(tags), returnFormat="WIDE", returnSize=minutes, includeBounds=True)
									cols = res.getColumnNames()
									historyValues = []
									prevValues = None
									for row in res:
										timestamp = row[0]
										rowValues = {}
										allNull = True
										for i in range(1, len(cols)):
											rowValues[cols[i]] = row[i]
											if row[i] != None:
												allNull = False
											
										if rowValues != prevValues and not allNull:
											prevValues = dict(rowValues)
											rowValues["t_stamp"] = timestamp
											historyValues.append(rowValues)
									
									i3x.utils.addChildrenHistory(elementObj, objs, historyValues)
						
						ret.append(bulkOk(elementObj, elementId=elementId))
					else:
						ret.append(bulkOk(obj, elementId=elementId))

			if not found:
				bulkError = True
				ret.append(bulkErr(404, "Element not found: %s" % elementId, elementId=elementId))
	
	return (200, bulkError, None, ret)

def _subscribeItem(subscription, elementId, maxDepth, udtInstances):
	# Expand to the element plus its composition descendants (per maxDepth) and
	# subscribe a listener to each, so every child streams its own update.
	expanded = i3x.utils.expandMonitoredItem(elementId, maxDepth, udtInstances)
	listeners = []
	for (listenElementId, tagPath, udtInstance) in expanded:
		listener = i3x.tag.subscribe(listenElementId, tagPath, udtInstance, subscription)
		listeners.append((tagPath, udtInstance, listener))
	subscription["listeners"][elementId] = listeners
	subscription["monitoredItems"][elementId] = maxDepth

def _unsubscribeItem(subscription, elementId):
	for (tagPath, udtInstance, listener) in subscription["listeners"].get(elementId, []):
		i3x.tag.unsubscribe(tagPath, udtInstance, listener)
	if elementId in subscription["listeners"]:
		del subscription["listeners"][elementId]
	if elementId in subscription["monitoredItems"]:
		del subscription["monitoredItems"][elementId]

def getSubscriptions(callType, requestData=None):
	log = system.util.getLogger("i3x.subscriptions")

	bulkError = False

	clientId = requestData.get("clientId", None)
	if clientId is None:
		return (400, False, "clientId is required", None)

	subscriptionIds = i3x.utils.getSubscriptions(clientId)
	if callType == "list":
		ret = []
		for subscriptionId in requestData.get("subscriptionIds", []):
			if subscriptionId in subscriptionIds:
				subscription = subscriptionIds[subscriptionId]
				monitoredObjects = [{"elementId":eid, "maxDepth":md} for eid, md in subscription["monitoredItems"].items()]
				obj = {"subscriptionId":subscriptionId, "displayName":subscription["displayName"], "monitoredObjects":monitoredObjects}
				ret.append(bulkOk(obj, subscriptionId=subscriptionId))
			else:
				bulkError = True
				ret.append(bulkErr(404, "Subscription not found: %s" % subscriptionId, subscriptionId=subscriptionId))
	elif callType == "create":
		displayName = requestData.get("displayName", clientId)
		subscriptionId = i3x.utils.createSubscription(clientId, displayName)
		ret = {"clientId":clientId, "subscriptionId":subscriptionId, "displayName":displayName}
	elif callType == "delete":
		ret = []
		for subscriptionId in requestData.get("subscriptionIds", []):
			if subscriptionId in subscriptionIds:
				subscription = subscriptionIds[subscriptionId]
				with subscription["lock"]:
					for elementId in list(subscription["monitoredItems"].keys()):
						_unsubscribeItem(subscription, elementId)
				i3x.utils.deleteSubscription(clientId, subscriptionId)
				ret.append(bulkOk(None, subscriptionId=subscriptionId))
			else:
				bulkError = True
				ret.append(bulkErr(404, "Subscription not found: %s" % subscriptionId, subscriptionId=subscriptionId))
	elif callType == "register":
		subscriptionId = requestData.get("subscriptionId", None)
		inElementIds = requestData.get("elementIds", [])
		maxDepth = requestData.get("maxDepth", 1)
		if maxDepth is None:
			maxDepth = 1

		if subscriptionId == None or subscriptionId not in subscriptionIds:
			return (404, False, "Subscription not found", None)

		ret = []
		udtInstances = i3x.ignition.getUdtInstances()
		validElementIds = set(inst["elementId"] for inst in udtInstances.values())
		subscription = subscriptionIds[subscriptionId]

		for elementId in inElementIds:
			if elementId not in validElementIds:
				bulkError = True
				ret.append(bulkErr(404, "Element not found: %s" % elementId, elementId=elementId, subscriptionId=subscriptionId))
			else:
				with subscription["lock"]:
					# Re-registering replaces the prior monitor so its listeners
					# are cleaned up rather than leaked.
					if elementId in subscription["monitoredItems"]:
						_unsubscribeItem(subscription, elementId)
					_subscribeItem(subscription, elementId, maxDepth, udtInstances)
				ret.append(bulkOk(None, elementId=elementId, subscriptionId=subscriptionId))
	elif callType == "unregister":
		subscriptionId = requestData.get("subscriptionId", None)
		inElementIds = requestData.get("elementIds", [])

		if subscriptionId == None or subscriptionId not in subscriptionIds:
			return (404, False, "Subscription not found", None)

		ret = []
		subscription = subscriptionIds[subscriptionId]
		for elementId in inElementIds:
			if elementId not in subscription["monitoredItems"]:
				bulkError = True
				ret.append(bulkErr(404, "Element not found: %s" % elementId, elementId=elementId, subscriptionId=subscriptionId))
			else:
				with subscription["lock"]:
					_unsubscribeItem(subscription, elementId)
				ret.append(bulkOk(None, elementId=elementId, subscriptionId=subscriptionId))
	elif callType == "sync":
		subscriptionId = requestData.get("subscriptionId", None)
		lastSequenceNumber = requestData.get("lastSequenceNumber", None)

		if subscriptionId == None or subscriptionId not in subscriptionIds:
			return (404, False, "Subscription not found", None)

		subscription = subscriptionIds[subscriptionId]
		with subscription["lock"]:
			batches = subscription["batches"]

			# Acknowledge: drop every batch at or below the client's high-water mark.
			if lastSequenceNumber != None:
				while batches and batches[0]["sequenceNumber"] <= lastSequenceNumber:
					batches.popleft()

			# Bundle everything staged since the last sync into one new batch.
			staged = subscription["stagedUpdates"]
			if len(staged):
				batch = {"sequenceNumber":subscription["sequenceNumber"], "updates":list(staged)}
				subscription["sequenceNumber"] += 1
				staged.clear()
				wasFull = batches.maxlen is not None and len(batches) == batches.maxlen
				batches.append(batch)
				if wasFull:
					subscription["overflow"] = True

			# 206 signals the client that some updates were dropped on overflow.
			overflow = subscription["overflow"]
			subscription["overflow"] = False
			ret = list(batches)

		return (206 if overflow else 200, False, None, ret)

	return (200, bulkError, None, ret)