SPEC_VERSION = "1.0"

def handleResponse(request, errorCode, isBulk, bulkError, error, result):
	resp = request["servletResponse"]
	
	if errorCode == 200:
		ret = {
			"success": not bulkError,
			"result" if not isBulk else "results": result
		}
		
		return {'json': system.util.jsonEncode(ret)}
	else:
		resp.setStatus(errorCode)
		
		ret = {
			"success": False,
			"error": {
				"code": errorCode,
				"message": error
			}
		}
		
		return {'json': system.util.jsonEncode(ret)}

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
					obj = relationships[elementId]
					ret.append({
						"success": True,
						"elementId": elementId,
						"result": obj,
						"error": None
					})
				else:
					bulkError = True
					ret.append({
						"success": False,
						"elementId": elementId,
						"result": None,
						"error": {
							"code": 404,
							"message": "Relationship type not found: %s" % elementId
						}
					})
		
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
						ret.append({
							"success": True,
							"elementId": elementId,
							"result": obj,
							"error": None
						})
					else:
						ret.append(obj)
		
		if isBulk and not foundElementId:
			bulkError = True
			ret.append({
				"success": False,
				"elementId": elementId,
				"result": None,
				"error": {
					"code": 404,
					"message": "Object type not found: %s" % elementId
				}
			})
	
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
						
						ret.append({
							"success": True,
							"elementId": elementId,
							"result": retObj,
							"error": None
						})
					elif callType == "value":
						elementObj = {"isComposition":udtInstance["isComposition"]}
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
							
						ret.append({
							"success": True,
							"elementId": elementId,
							"result": elementObj,
							"error": None
						})
					elif callType == "history":
						elementObj = {"values":[], "isComposition":udtInstance["isComposition"]}
						
						if udtInstance["typeId"] == "ignition-alarm":
							startTime = system.date.parse(startTime, i3x.ignition.DATE_FORMAT)
							endTime = system.date.parse(endTime, i3x.ignition.DATE_FORMAT)
							res = system.alarm.queryJournal(startTime, endTime, journalName="Journal", source=udtInstancePath)
							for row in res:
								alarmObj = i3x.ignition.getAlarmObj(row)
								elementObj["values"].append({"value":alarmObj, "quality":"Good", "timestamp":alarmObj["eventTime"], "isComposition":False})
						elif udtInstance["typeId"] != "folder-type" and udtInstance["typeId"] != "ignition-tag-provider":
							startTime = i3x.utils.getLocalTime(startTime)
							endTime = i3x.utils.getLocalTime(endTime)
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
						
						ret.append({
							"success": True,
							"elementId": elementId,
							"result": elementObj,
							"error": None
						})
					else:
						ret.append({
							"success": True,
							"elementId": elementId,
							"result": obj,
							"error": None
						})
						
			if not found:
				bulkError = True
				ret.append({
					"success": False,
					"elementId": elementId,
					"result": None,
					"error": {
						"code": 404,
						"message": "Element not found: %s" % elementId
					}
				})
	
	return (200, bulkError, None, ret)
	
def getSubscriptions(callType, requestData=None):
	log = system.util.getLogger("i3x.subscriptions")
	
	bulkError = False
	
	clientId = requestData.get("clientId", None)
	if clientId == None:
		clientId = "None"
		#return (404, bulkError, "Client Id not specified", {})
	
	subscriptionIds = i3x.utils.getSubscriptions(clientId)
	if callType == "list":
		ret = []
		inSubscriptionIds = requestData.get("subscriptionIds", [])
		subscriptions = []
		for subscriptionId in inSubscriptionIds:
			if subscriptionId in subscriptionIds:
				subscription = subscriptionIds[subscriptionId]
				obj = {"subscriptionId":subscriptionId, "displayName":subscription["displayName"], "monitoredObjects":[{"elementId":elementId, "maxDepth":1} for elementId in subscription["elementIds"]]}
				ret.append({
					"success": True,
					"subscriptionId": subscriptionId,
					"result": obj,
					"error": None
				})
			else:
				bulkError = True
				ret.append({
					"success": False,
					"subscriptionId": subscriptionId,
					"result": None,
					"error": {
						"code": 404,
						"message": "Subscription not found: %s" % subscriptionId
					}
				})
	elif callType == "create":
		displayName = requestData.get("displayName", clientId)
		ret = {}
		ret["clientId"] = clientId
		ret["displayName"] = displayName
		ret["subscriptionId"] = i3x.utils.createSubscription(clientId, displayName)
	elif callType == "delete":
		ret = []
		inSubscriptionIds = requestData.get("subscriptionIds", [])
		subscriptions = []
		for subscriptionId in inSubscriptionIds:
			if subscriptionId in subscriptionIds:
				udtInstances = i3x.ignition.getUdtInstances()
				subscription = subscriptionIds[subscriptionId]
				for elementId in subscription["elementIds"]:
					tagPath = i3x.utils.elementIdToPath(elementId)
					udtInstance = udtInstances[tagPath]
					i3x.tag.unsubscribe(elementId, tagPath, udtInstance, subscription)
				
				i3x.utils.deleteSubscription(clientId, subscriptionId)
				
				ret.append({
					"success": True,
					"subscriptionId": subscriptionId,
					"result": None,
					"error": None
				})
			else:
				bulkError = True
				ret.append({
					"success": False,
					"subscriptionId": subscriptionId,
					"result": None,
					"error": {
						"code": 404,
						"message": "Subscription not found: %s" % subscriptionId
					}
				})
	elif callType == "register":
		subscriptionId = requestData.get("subscriptionId", None)
		inElementIds = requestData.get("elementIds", [])
		
		if subscriptionId == None or subscriptionId not in subscriptionIds:
			return (404, bulkError, "Subscription not found", {})
		else:
			ret = []
			udtInstances = i3x.ignition.getUdtInstances()
			elementIds = [objValue["elementId"] for objKey, objValue in udtInstances.iteritems()]
			
			subscription = subscriptionIds[subscriptionId]
			for elementId in inElementIds:
				if elementId not in elementIds:
					bulkError = True
					ret.append({
						"success": False,
						"subscriptionId": subscriptionId,
						"elementId": elementId,
						"result": None,
						"error": {
							"code": 404,
							"message": "Element not found: %s" % elementId
						}
					})
				else:
					subscription["elementIds"].append(elementId)
					tagPath = i3x.utils.elementIdToPath(elementId)
					udtInstance = udtInstances[tagPath]
					i3x.tag.subscribe(elementId, tagPath, udtInstance, subscription)
					ret.append({
						"success": True,
						"subscriptionId": subscriptionId,
						"elementId": elementId,
						"result": None,
						"error": None
					})
	elif callType == "unregister":
		subscriptionId = requestData.get("subscriptionId", None)
		inElementIds = requestData.get("elementIds", [])
		
		if subscriptionId == None or subscriptionId not in subscriptionIds:
			return (404, bulkError, "Subscription not found", {})
		else:
			ret = []
			udtInstances = i3x.ignition.getUdtInstances()
			elementIds = [objValue["elementId"] for objKey, objValue in udtInstances.iteritems()]
			
			subscription = subscriptionIds[subscriptionId]
			for elementId in inElementIds:
				if elementId not in subscription["elementIds"]:
					bulkError = True
					ret.append({
						"success": False,
						"subscriptionId": subscriptionId,
						"elementId": elementId,
						"result": None,
						"error": {
							"code": 404,
							"message": "Element not found: %s" % elementId
						}
					})
				else:
					tagPath = i3x.utils.elementIdToPath(elementId)
					udtInstance = udtInstances[tagPath]
					i3x.tag.unsubscribe(elementId, tagPath, udtInstance, subscription)
					ret.append({
						"success": True,
						"subscriptionId": subscriptionId,
						"elementId": elementId,
						"result": None,
						"error": None
					})
					
			subscription["elementIds"] = [elementId for elementId in subscription["elementIds"] if elementId not in inElementIds]
			subscriptionIds[subscriptionId]["queuedUpdates"].clear()
	elif callType == "sync":
		subscriptionId = requestData.get("subscriptionId", None)
		lastSequenceNumber = requestData.get("lastSequenceNumber", None)
		
		if subscriptionId == None or subscriptionId not in subscriptionIds:
			return (404, bulkError, "Subscription not found", {})
		else:
			subscription = subscriptionIds[subscriptionId]
			if lastSequenceNumber != None:
				idx = -1
				for row in list(subscription["queuedUpdates"]):
					if row["sequenceNumber"] <= lastSequenceNumber:
						idx += 1
			
				if idx > -1:
					for _ in range(idx+1):
						subscriptionIds[subscriptionId]["queuedUpdates"].popleft()
				
			ret = list(subscription["queuedUpdates"])
			
	return (200, bulkError, None, ret)