# --- Timestamps -------------------------------------------------------------
# All i3X timestamps are RFC 3339 UTC (e.g. "2026-06-30T12:00:00.000Z").
# parseUtc turns an incoming string into an absolute java.util.Date (no zone
# assumptions); formatUtc renders any java.util.Date back as UTC. The previous
# implementation hard-coded America/Los_Angeles, which corrupted timestamps on
# any gateway not running in Pacific time.

def parseUtc(utcTime):
	from java.time import Instant
	from java.util import Date
	if utcTime is None:
		return None
	# Date.from(...) can't be called from Jython ("from" is a keyword), so build
	# the Date from epoch millis instead.
	return Date(Instant.parse(utcTime).toEpochMilli())

def formatUtc(date):
	from java.time import ZoneOffset
	from java.time.format import DateTimeFormatter
	if date is None:
		return None
	formatter = DateTimeFormatter.ofPattern(i3x.ignition.DATE_FORMAT).withZone(ZoneOffset.UTC)
	return formatter.format(date.toInstant())

# --- Error helpers ----------------------------------------------------------
# The i3X spec models errors as ErrorDetail {title, status, detail}.
REASON_PHRASES = {
	400: "Bad Request",
	401: "Unauthorized",
	403: "Forbidden",
	404: "Not Found",
	409: "Conflict",
	500: "Internal Server Error",
	501: "Not Implemented",
	503: "Service Unavailable"
}

def errorDetail(status, detail, title=None):
	return {
		"title": title if title else REASON_PHRASES.get(status, "Error"),
		"status": status,
		"detail": detail if detail else REASON_PHRASES.get(status, "Error")
	}

# --- Model cache ------------------------------------------------------------
# The structural model (instances, type schemas) is expensive to rebuild on
# every request. We cache it briefly in gateway globals. Live values, history
# and alarm status are always read fresh; only the structure map is cached.
CACHE_TTL_MS = 5000

def getCacheStore():
	from threading import RLock
	g = system.util.getGlobals()
	store = g.get("i3x.cache", None)
	if store is None:
		store = {"data": {}, "lock": RLock()}
		g["i3x.cache"] = store
	return store

def cacheGet(key):
	from java.lang import System
	store = getCacheStore()
	with store["lock"]:
		entry = store["data"].get(key, None)
		if entry is None:
			return None
		expiry, value = entry
		if System.currentTimeMillis() > expiry:
			return None
		return value

def cacheSet(key, value, ttlMs=CACHE_TTL_MS):
	from java.lang import System
	store = getCacheStore()
	with store["lock"]:
		store["data"][key] = (System.currentTimeMillis() + ttlMs, value)

def cacheClear():
	store = getCacheStore()
	with store["lock"]:
		store["data"].clear()

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
	# Built-in types are registered under their literal ids; only real UDT type
	# paths get base64-encoded into elementIds. Encoding the built-ins here would
	# make typeElementId fail to resolve against GET /objecttypes.
	if typeId not in ["ignition-alarm", "folder-type", "ignition-tag-provider"]:
		typeId = pathToElementId(typeId)
	obj = {"elementId":udtInstance["elementId"], "typeElementId":typeId, "displayName":udtInstance["name"], "parentId":udtInstance["parentId"], "isComposition":udtInstance["isComposition"], "isExtended":len(udtInstance["parameters"]) > 0}
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
	from collections import deque, OrderedDict
	from threading import RLock

	subscriptions = getSubscriptions(clientId)
	uuid = str(UUID.randomUUID())

	subscriptions[uuid] = {
		"displayName": displayName,
		"created": system.date.now(),
		# requested elementId -> maxDepth
		"monitoredItems": OrderedDict(),
		# requested elementId -> [(tagPath, udtInstance, listener), ...]
		"listeners": {},
		# SyncUpdateEntry dicts awaiting the next sync()
		"stagedUpdates": deque(maxlen=i3x.tag.MAX_QUEUE_SIZE),
		# SyncBatch dicts already handed to (or pending for) the client
		"batches": deque(maxlen=i3x.tag.MAX_QUEUE_SIZE),
		"sequenceNumber": 1,
		"overflow": False,
		"lock": RLock()
	}
	return uuid

def expandMonitoredItem(elementId, maxDepth, udtInstances):
	# Returns [(elementId, tagPath, udtInstance), ...] for the element and its
	# HasComponent descendants, honouring maxDepth (1=self only, 0=infinite).
	# Folders and tag providers have no value and are skipped (we still descend
	# through them). This lets each composition child stream its own update.
	ret = []
	tagPath = elementIdToPath(elementId)
	if tagPath not in udtInstances:
		return ret

	def recurse(inst, depth):
		if inst["typeId"] not in ("folder-type", "ignition-tag-provider"):
			ret.append((inst["elementId"], inst["path"], inst))
		if depth < maxDepth or maxDepth == 0:
			for childElementId in inst.get("relationships", {}).get("HasComponent", []):
				childPath = elementIdToPath(childElementId)
				if childPath in udtInstances:
					recurse(udtInstances[childPath], depth + 1)

	recurse(udtInstances[tagPath], 1)
	return ret

def deleteSubscription(clientId, subscriptionId):
	subscriptions = getSubscriptions(clientId)
	del subscriptions[subscriptionId]