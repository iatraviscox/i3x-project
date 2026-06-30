def getLocalTime(utcTime):
	from java.time import Instant
	from java.time import ZoneId
	from java.time import ZonedDateTime
	from java.util import Date
	from java.time.format import DateTimeFormatter
	
	instant = Instant.parse(utcTime)
	localZone = ZoneId.of("America/Los_Angeles")
	localTime = instant.atZone(localZone)
	formatter = DateTimeFormatter.ofPattern(i3x.ignition.DATE_FORMAT)
	localTime = localTime.format(formatter)
	return system.date.parse(localTime, i3x.ignition.DATE_FORMAT)

def setStatus(request, code, error):
	response = request['servletResponse']
	response.setStatus(code)
	return {"json":system.util.jsonEncode(error)}

def pathToElementId(path):
	from java.util import Base64
	return Base64.getUrlEncoder().withoutPadding().encodeToString(path)

def elementIdToPath(elementId):
	from java.util import Base64
	from java.lang import String
	from java.nio.charset import StandardCharsets
	return str(String(Base64.getUrlDecoder().decode(elementId), StandardCharsets.UTF_8))

def tagPathGen1ToGen2(tagPath):
	import re
	match = re.search(r"\[(.*?)\]", tagPath)
	tagProvider = "default"
	if match:
		tagProvider = match.group(1)
		tagPath = re.sub(r"\[.*?\]", "", tagPath)
	return "prov:%s:/tag:%s" % (tagProvider, tagPath)
	
def tagPathGen2ToGen1(tagPath):
	parts = tagPath.split(":/")
	if len(parts) > 1:
		tagPath = "[%s]%s" % (parts[0].replace("prov:", ""), parts[1].replace("tag:", ""))
	else:
		tagPath = "[default]%s" % parts[0].replace("tag:", "")
	return tagPath
	
def alarmSourceToStateTagPath(source):
	parts = source.split(":/")
	return "[%s]%s/Alarms/%s.State" % (parts[0].replace("prov:", ""), parts[1].replace("tag:", ""), parts[2].replace("alm:", ""))

def getTagProviderFromPath(path):
	import re
	match = re.search(r"\[(.*?)\]", path)
	if match:
		return match.group(1)
	return None
	
def getTagNameFromPath(path):
	import re
	if path != None and path != "":
		pathParts = path.split("/")
		tagName = re.sub(r"\[.*?\]", "", pathParts[-1])
		return tagName
		
	return None

def getNamespaceUriParam(row):
	from com.inductiveautomation.ignition.common.tags.config.properties import ParameterValue
	from com.inductiveautomation.ignition.common.sqltags.model.types import DataTypeClass
	if "parameters" in row and row["parameters"] != None:
		paramValue = row["parameters"].get("NamespaceUri", ParameterValue(DataTypeClass.String, i3x.ignition.IgnitionNamespaceUri))
		return paramValue if isinstance(paramValue, basestring) else paramValue.value
	else:
		return i3x.ignition.IgnitionNamespaceUri
	
def buildUdtInstanceObj(udtInstance, includeMetadata):
	typeId = udtInstance["typeId"]
	if typeId not in ["ignition-alarm"]:
		typeId = pathToElementId(typeId)
	obj = {"elementId":udtInstance["elementId"], "typeElementIdId":typeId, "displayName":udtInstance["name"], "parentId":udtInstance["parentId"], "isComposition":udtInstance["isComposition"], "isExtended":len(udtInstance["parameters"]) > 0}
	if includeMetadata:
		obj["metadata"] = {
			"typeNamespaceUri": udtInstance["namespaceUri"],
			"sourceTypeId":typeId
		}
		
		if len(udtInstance["relationships"]):
			obj["metadata"]["relationships"] = udtInstance["relationships"]
		
		if len(udtInstance["parameters"]):
			obj["metadata"]["system"] = {
				"parameters": udtInstance["parameters"]
			}
		
	return obj

def getRelatedObjects(filterRelationshipType, relationshipType, obj, udtInstances, includeMetadata):
	ret = []
	
	if filterRelationshipType == None or filterRelationshipType == relationshipType:
		if relationshipType in obj["relationships"]:
			if isinstance(obj["relationships"][relationshipType], list):
				for rChildPath in obj["relationships"][relationshipType]:
					rObj = i3x.utils.buildUdtInstanceObj(udtInstances[i3x.utils.elementIdToPath(rChildPath)], includeMetadata)
					ret.append({
						"sourceRelationship":relationshipType,
						"object":rObj
					})
			else:
				if obj["relationships"][relationshipType] != "/":
					rObj = i3x.utils.buildUdtInstanceObj(udtInstances[i3x.utils.elementIdToPath(obj["relationships"][relationshipType])], includeMetadata)
					ret.append({
						"sourceRelationship":relationshipType,
						"object":rObj
					})

	return ret

def getChildrenObjects(obj, relationshipType):
	ret = []
	if relationshipType in obj["relationships"]:
		ret = [i3x.utils.elementIdToPath(rChildPath) for rChildPath in obj["relationships"][relationshipType]]
	return ret

def getChildrenObjectNames(obj, relationshipType):
	ret = []
	objPath = obj["path"] + "/"
	if relationshipType in obj["relationships"]:
		ret = [i3x.utils.elementIdToPath(rChildPath).replace(objPath, "") for rChildPath in obj["relationships"][relationshipType]]
	return ret

def removeChildren(objValue, children):
	ret = {}
	keysToRemove = []
	
	for child in children:
		parts = child.split("/")
		if parts[0] in objValue and parts[0] not in keysToRemove:
			keysToRemove.append(parts[0])
		
		childValue = objValue
		for part in parts:
			if part not in childValue:
				childValue = None
				break
			else:
				childValue = childValue[part]

		ret[child] = childValue
	
	for key in keysToRemove:
		del objValue[key]
	
	return ret
	
def addChildrenValues(udtInstances, udtInstance, elementObj, childrenValues, quality, timestamp, currentDepth, maxDepth):
	if currentDepth <= maxDepth or maxDepth == 0:
		objPath = udtInstance["path"] + "/"
		children = getChildrenObjects(udtInstance, "HasComponent")
		for child in children:
			childName = child.replace(objPath, "")
			childElementId = pathToElementId(child)
			subChildrenValues = {}
			value = childrenValues.get(childName, None)
			if value == None:
				value = {"isComposition":udtInstances[child]["isComposition"]}
			else:
				subChildren = getChildrenObjectNames(udtInstances[child], "HasComponent")
				subChildrenValues = removeChildren(value, subChildren)
				value = {"value":value, "quality":quality, "timestamp":timestamp, "isComposition":udtInstances[child]["isComposition"]}
			
			if "components" not in elementObj:
				elementObj["components"] = {}
				
			elementObj["components"][childElementId] = value
			addChildrenValues(udtInstances, udtInstances[child], elementObj["components"][childElementId], subChildrenValues, quality, timestamp, currentDepth + 1, maxDepth)

def getTags(path, objs, tags, currentDepth=1, maxDepth=1):
	ret = []
	if currentDepth <= maxDepth or maxDepth == 0:
		for tag in tags:
			tagPath = "%s/%s" % (path, tag["path"])
			tagType = str(tag["tagType"])
			
			if tagType == "Folder":
				ret.extend(getTags(tagPath, objs, tag["tags"], currentDepth, maxDepth))
			elif tagType == "UdtInstance":
				if (currentDepth + 1) <= maxDepth or maxDepth == 0:
					subObj = {"tags":[], "objects":{}}
					objs["objects"][tagPath] = subObj
					ret.extend(getTags(tagPath, subObj, tag["tags"], currentDepth+1, maxDepth))
			elif tagType == "AtomicTag":
				tp = tagPathGen1ToGen2(tagPath)
				ret.append(tp)
				objs["tags"].append(tp)
			
	return ret
	
def addChildrenHistory(elementObj, objs, historyValues):
	if len(objs["tags"]):
		for row in historyValues:
			rowValues = {}
			for tag in objs["tags"]:
				tagPath = tagPathGen2ToGen1(tag)
				tagName = getTagNameFromPath(tagPath)
				rowValues[tagName] = row[tag]
			elementObj["values"].append({"value":rowValues, "quality":"Good", "timestamp":system.date.format(row["t_stamp"], i3x.ignition.DATE_FORMAT)})
			
	if len(objs["objects"]):
		elementObj["isComposition"] = True
		for obj in objs["objects"]:
			subObjs = objs["objects"][obj]
			subElementObj = {"values":[], "isComposition":False}
			
			if "components" not in elementObj:
				elementObj["components"] = {}
			
			elementObj["components"][pathToElementId(tagPathGen2ToGen1(obj))] = subElementObj
			addChildrenHistory(subElementObj, subObjs, historyValues)
			
def getSubscriptions(clientId=None):
	globalsObj = system.util.getGlobals()
	
	if "i3x.subscriptions" not in globalsObj:
		globalsObj["i3x.subscriptions"] = {}
		
	if clientId != None and clientId not in globalsObj["i3x.subscriptions"]:
		globalsObj["i3x.subscriptions"][clientId] = {}
		
	return globalsObj["i3x.subscriptions"][clientId]
	
def createSubscription(clientId, displayName):
	from java.util import UUID
	from collections import deque
	
	subscriptions = getSubscriptions(clientId)
	uuid = str(UUID.randomUUID())
	
	subscriptions[uuid] = {"displayName":displayName, "created":system.date.now(), "elementIds":[], "isStreaming":False, "queuedUpdates":deque(maxlen=i3x.tag.MAX_QUEUE_SIZE), "listeners":{}, "sequenceNumber":1}
	return uuid

def deleteSubscription(clientId, subscriptionId):
	subscriptions = getSubscriptions(clientId)
	del subscriptions[subscriptionId]