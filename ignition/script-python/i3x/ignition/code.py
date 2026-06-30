IgnitionNamespaceUri = "https://inductiveautomation.com/UDT"
UaCoreUri = "http://opcfoundation.org/UA/"
DATE_FORMAT = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"

def getTagProviders():
	tagProviders = []
	res = system.tag.browse("")
	for row in res.getResults():
		tagProviders.append(row["name"])
	return tagProviders

def getUdtDefs(tagProvider, elementId=None):
	query = {
	  "options": {
	    "includeUdtMembers": True,
	    "includeUdtDefinitions": True
	  },
	  "condition": {
	    "tagType": "UdtType",
	    "attributes": {
	      "values": [],
	      "requireAll": True
	    }
	  },
	  "returnProperties": [
	    "tooltip",
	    "documentation",
	    "parameters",
	    "tagType",
	    "quality"
	  ]
	}
	
	if elementId != None:
		query["condition"]["path"] = elementId
	
	return system.tag.query(tagProvider, query)
	
def getUdtInstancesForTagProvider(tagProvider):
	query = {
	  "options": {
	    "includeUdtMembers": True,
	    "includeUdtDefinitions": False
	  },
	  "condition": {
	    "tagType": "UdtInstance",
	    "attributes": {
	      "values": [],
	      "requireAll": True
	    }
	  },
	  "returnProperties": [
	    "tooltip",
	    "documentation",
	    "parameters",
	    "tagType",
	    "quality"
	  ]
	}
	
	return system.tag.query(tagProvider, query)

def addFolders(tagProvider, udtInstances, parentPath):
	if parentPath != "":
		parentPathParts = parentPath.split("/")
		for i in range(len(parentPathParts)):
			path = "/".join(parentPathParts[0:i+1])
			if path not in udtInstances:
				parentParentPath = "/".join(path.split("/")[:-1])
				if parentParentPath == "":
					parentParentPath = "[%s]" % tagProvider
				name = path.split("/")[-1]
				if "[%s]" % tagProvider in name:
					name = name.replace("[%s]" % tagProvider, "")
				udtInstances[path] = {"path":path, "elementId":i3x.utils.pathToElementId(path), "type":"folder", "tagProvider":tagProvider, "parentPath":parentParentPath, "parentUdt":None, "childrenUdts":[], "alarms":[], "namespaceUri":i3x.ignition.UaCoreUri, "typeId":"folder-type", "name":name, "parameters":{}, "alarmObj":{}}
	
def findUdtParent(udtInstances, udtInstancePath, udtInstance):
	parentPath = udtInstance["parentPath"]
	
	if parentPath != "":
		if udtInstances[parentPath]["type"] == "udt":
			udtInstance["parentUdt"] = parentPath
			if udtInstance["typeId"] == "ignition-alarm":
				udtInstances[parentPath]["alarms"].append(udtInstancePath)
			else:
				udtInstances[parentPath]["childrenUdts"].append(udtInstancePath)
		else:
			parentPath = udtInstances[parentPath]["parentPath"]
			found = False
			while parentPath != "":
				if udtInstances[parentPath]["type"] == "udt":
					udtInstance["parentUdt"] = parentPath
					if udtInstance["typeId"] == "ignition-alarm":
						udtInstances[parentPath]["alarms"].append(udtInstancePath)
					else:
						udtInstances[parentPath]["childrenUdts"].append(udtInstancePath)
						
					found = True
					break
				
				parentPath = udtInstances[parentPath]["parentPath"]
			
			if not found and udtInstance["parentPath"] != "":
				if udtInstance["typeId"] == "ignition-alarm":
					udtInstances[udtInstance["parentPath"]]["alarms"].append(udtInstancePath)
				else:
					udtInstances[udtInstance["parentPath"]]["childrenUdts"].append(udtInstancePath)

def getAlarmDetails(row, key):
	if key == "ackData":
		obj = row.getAckData()
	elif key == "clearedData":
		obj = row.getClearedData()
	else:
		obj = row.getActiveData()
	
	data = dict(obj.getRawValueMap()) if obj != None else {}
	newData = {}
	for k, v in data.items():
		if str(k) == "ackUser":
			val = None if v is None else v.toString()
		elif str(k) == "eventTime":
			val = i3x.utils.formatUtc(v)
		else:
			val = v
		newData[str(k)] = val
	if "mode" in newData:
		del newData["mode"]
	return newData

def getAlarmObj(row):
	alarmObj = {}
	alarmObj["source"] = str(row.getSource())
	alarmObj["name"] = row.getName()
	alarmObj["eventId"] = str(row.eventId)
	alarmObj["displayPath"] = row.getDisplayPath().toString()
	alarmObj["count"] = row.getCount()
	alarmObj["label"] = row.getLabel()
	alarmObj["lastEventState"] = row.getLastEventState().name()
	alarmObj["notes"] = row.getNotes() 
	alarmObj["priority"] = row.getPriority().name()
	alarmObj["state"] = row.getState().name() 
	alarmObj["isActive"] = row.isActive
	alarmObj["isAcked"] = row.isAcked()
	alarmObj["isCleared"] = row.isCleared()
	alarmObj["isShelved"] = row.isShelved()
	alarmObj["ackData"] = getAlarmDetails(row, "ackData")
	alarmObj["clearedData"] = getAlarmDetails(row, "clearedData")
	alarmObj["activeData"] = getAlarmDetails(row, "activeData")
	
	eventTime = None
	if row.getState().name() == "ActiveUnacked":
		eventTime = alarmObj["activeData"]["eventTime"]
	elif row.getState().name() == "ActiveAcked":
		eventTime = alarmObj["ackData"]["eventTime"]
	elif row.getState().name() == "ClearUnacked":
		eventTime = alarmObj["clearedData"]["eventTime"]
	elif row.getState().name() == "ClearAcked":
		eventTime = alarmObj["ackData"]["eventTime"]
		
	alarmObj["eventTime"] = eventTime
		
	return alarmObj

def parseAlarms(res):
	alarms = {}
	for row in res:
		source = str(row.getSource())
		tagPath = i3x.utils.tagPathGen2ToGen1(str(row.getSource()))
		tagProvider = i3x.utils.getTagProviderFromPath(tagPath)
		name = row.getName()
		alarmObj = getAlarmObj(row)
		rowObj = {"path":source, "elementId":i3x.utils.pathToElementId(source), "type":"udt", "tagProvider":tagProvider, "parentPath":tagPath, "parentUdt":None, "childrenUdts":[], "alarms":[], "namespaceUri":i3x.ignition.IgnitionNamespaceUri, "typeId":"ignition-alarm", "name":name, "parameters":{}, "alarmObj":alarmObj}
		
		if source not in alarms:
			alarms[source] = rowObj
		elif system.date.isAfter(i3x.utils.parseUtc(alarmObj["eventTime"]), i3x.utils.parseUtc(alarms[source]["alarmObj"]["eventTime"])):
			alarms[source] = rowObj
	return alarms

def getAlarms(tagProvider):
	res = system.alarm.queryStatus(provider=[tagProvider])
	alarms = parseAlarms(res)
	return alarms
	
def getAlarmFromSource(source):
	res = system.alarm.queryStatus(source=[source])
	alarms = parseAlarms(res)		
	return alarms[source]

def getUdtInstances():
	# The structural model is expensive to build (browses every provider, every
	# UDT instance, and queries alarm status). Cache it briefly so a burst of
	# requests doesn't rebuild it each time. Live values/history are read fresh
	# elsewhere; only the structure (and last-known alarm status) is cached.
	cached = i3x.utils.cacheGet("udtInstances")
	if cached is not None:
		return cached

	ret = {}

	tagProviders = getTagProviders()
	for tagProvider in tagProviders:
		tpPath = "[%s]" % tagProvider
		tpTypes = "[%s]_types_/" % tagProvider
		udtInstances = {}
		udtInstances[tpPath] = {"path":tpPath, "elementId":i3x.utils.pathToElementId(tpPath), "type":"folder", "tagProvider":tagProvider, "parentPath":"", "parentUdt":None, "childrenUdts":[], "alarms":[], "namespaceUri":i3x.ignition.IgnitionNamespaceUri, "typeId":"ignition-tag-provider", "name":tagProvider, "parameters":{}, "alarmObj":{}}
		
		alarms = getAlarms(tagProvider)
		for alarmTagPath in alarms:
			alarm = alarms[alarmTagPath]
			udtInstances[alarm["path"]] = alarm
		
		res = i3x.ignition.getUdtInstancesForTagProvider(tagProvider)
		for row in res:
			udtPath = str(row["fullPath"])
			pathParts = udtPath.split("/")
			parentPath = "/".join(pathParts[:-1])
			if parentPath == "":
				parentPath = "[%s]" % tagProvider
			elementId = i3x.utils.pathToElementId(udtPath)
			dtTypeId = "%s%s" % (tpTypes, row["typeId"])
			
			parameters = {}
			if "parameters" in row and row["parameters"] != None and len(row["parameters"]) > 0:
				for param in row["parameters"]:
					paramValue = row["parameters"][param]
					parameters[param] = paramValue if isinstance(paramValue, basestring) else paramValue.value
			
			udtInstances[udtPath] = {"path":udtPath, "elementId":elementId, "type":"udt", "tagProvider":tagProvider, "parentPath":parentPath, "parentUdt":None, "childrenUdts":[], "alarms":[], "namespaceUri":i3x.utils.getNamespaceUriParam(row), "typeId":dtTypeId, "name":row["name"], "parameters":parameters, "alarmObj":{}}
		
		# We need to expand to all of the folders from the path
		for udtInstancePath in udtInstances:
			udtInstance = udtInstances[udtInstancePath]
			addFolders(tagProvider, udtInstances, udtInstance["parentPath"])
		
		# We need to find the UDT parent if exists
		for udtInstancePath in udtInstances:
			udtInstance = udtInstances[udtInstancePath]
			findUdtParent(udtInstances, udtInstancePath, udtInstance)
		
		# We need to update all of the relationships
		for udtInstancePath in udtInstances:
			udtInstance = udtInstances[udtInstancePath]
			
			if udtInstance["parentUdt"] != None:
				parentId = i3x.utils.pathToElementId(udtInstance["parentUdt"])
			else:
				parentId = None if udtInstance["parentPath"] == "" else i3x.utils.pathToElementId(udtInstance["parentPath"])
				
			relationships = {}
			
			if udtInstance["typeId"] == "ignition-alarm":
				relationships["AlarmOf"] = parentId
			elif parentId != None:
				relationships["HasParent"] = parentId
			
			if udtInstance["type"] == "folder" and len(udtInstance["childrenUdts"]) > 0:
				relationships["HasChildren"] = [i3x.utils.pathToElementId(path) for path in udtInstance["childrenUdts"]]
			elif udtInstance["type"] == "udt" and len(udtInstance["childrenUdts"]) > 0:
				relationships["HasComponent"] = [i3x.utils.pathToElementId(path) for path in udtInstance["childrenUdts"] if not (udtInstances[path]["typeId"] == "folder-type" and udtInstances[path]["parentUdt"] != None)]
				
			if len(udtInstance["alarms"]) > 0:
				relationships["HasAlarm"] = [i3x.utils.pathToElementId(path) for path in udtInstance["alarms"]]
			
			if udtInstance["type"] == "udt" and udtInstance["parentPath"] != "" and udtInstances[udtInstance["parentPath"]]["type"] == "udt":
				relationships["ComponentOf"] = i3x.utils.pathToElementId(udtInstance["parentPath"])
			
			udtInstance["parentId"] = parentId
			udtInstance["relationships"] = relationships
			udtInstance["isComposition"] = udtInstance["type"] == "udt" and len(udtInstance["childrenUdts"]) > 0

		# Ensure every relationship is stored bidirectionally so the graph is
		# traversable from either node (spec: "All relationships MUST be stored
		# bidirectionally"). This fills missing reverse edges - e.g. the
		# HasChildren reverse of a child's HasParent on a UDT parent - without
		# overwriting any to-one edge already set above.
		REVERSE = {"HasParent":"HasChildren", "HasChildren":"HasParent", "HasComponent":"ComponentOf", "ComponentOf":"HasComponent", "HasAlarm":"AlarmOf", "AlarmOf":"HasAlarm"}
		TO_MANY = ("HasChildren", "HasComponent", "HasAlarm")
		byElementId = {}
		for udtInstancePath in udtInstances:
			byElementId[udtInstances[udtInstancePath]["elementId"]] = udtInstances[udtInstancePath]

		for udtInstancePath in udtInstances:
			udtInstance = udtInstances[udtInstancePath]
			srcId = udtInstance["elementId"]
			for rel, targets in list(udtInstance["relationships"].items()):
				if rel not in REVERSE:
					continue
				rev = REVERSE[rel]
				targetList = targets if isinstance(targets, list) else [targets]
				for tgt in targetList:
					if tgt == None or tgt == "/" or tgt not in byElementId:
						continue
					targetRels = byElementId[tgt]["relationships"]
					if rev in TO_MANY:
						existing = targetRels.get(rev)
						if existing == None:
							targetRels[rev] = [srcId]
						elif isinstance(existing, list):
							if srcId not in existing:
								existing.append(srcId)
						elif existing != srcId:
							targetRels[rev] = [existing, srcId]
					elif rev not in targetRels:
						# to-one reverse: fill only if absent, never overwrite
						targetRels[rev] = srcId

		ret.update(udtInstances)

	i3x.utils.cacheSet("udtInstances", ret)
	return ret

def parseTags(path, config):
	tagProvider = path.split("/")[0]
	DATA_TYPE_MAPPINGS = {"Int1":"integer", "Int2":"integer", "Int4":"integer", "Int8":"integer", "Float4":"number", "Float8":"number", "Boolean":"boolean", "String":"string", "DateTime":"string", "Int1Array":"array", "Int2Array":"array", "Int4Array":"array", "Int8Array":"array", "Float4Array":"array", "Float8Array":"array", "StringArray":"array", "DateTimeArray":"array", "ByteArray":"array", "DataSet":"string", "Document":"object"}
	
	types = []
	tags = {}
	if "tags" in config:
		for row in config["tags"]:
			name = row["name"]
			tagType = str(row["tagType"])
			dataType = str(row.get("dataType", "Int4"))
			
			newPath = "%s/%s" % (path, row["path"])
			
			if tagType == "AtomicTag":
				tag = {"type":[DATA_TYPE_MAPPINGS.get(dataType, "string"), "null"]}
				
				if "tooltip" in row and row["tooltip"] != None and row["tooltip"] != "":
					tag["description"] = row["tooltip"]
				
				if "value" in row:
					if dataType == "DateTime":
						tag["default"] = i3x.utils.formatUtc(row["value"])
					elif dataType == "DateTimeArray":
						newVal = []
						for val in row["value"]:
							newVal.append(i3x.utils.formatUtc(val))
						tag["default"] = newVal
					elif dataType == "DataSet":
						tag["default"] = system.dataset.toCSV(row["value"], True)
					elif dataType == "Document":
						tag["default"] = row["value"].toDict()
					else:
						tag["default"] = row["value"]
					
				if "engUnit" in row:
					tag["engUnit"] = row["engUnit"]
					
				if "engLow" in row:
					tag["engLow"] = row["engLow"]
					
				if "engHigh" in row:
					tag["engHigh"] = row["engHigh"]
				
				tags[row["name"]] = tag
			elif tagType == "Folder":
				(subTypes, subTags) = parseTags(newPath, row)
				tag = {
					"type":"object",
					"properties":subTags
				}
				
				if "tooltip" in row and row["tooltip"] != None and row["tooltip"] != "":
					tag["description"] = row["tooltip"]
				
				tags[row["name"]] = tag
				
				for subType in subTypes:
					if subType not in types:
						types.append(subType)
			elif tagType == "UdtInstance":
				dtPath = i3x.utils.pathToElementId("%s/%s" % (tagProvider, row["typeId"]))
				types.append(dtPath)
				
				tag = {"$ref":"#/types/%s" % (dtPath)}
				
				if "tooltip" in row and row["tooltip"] != None and row["tooltip"] != "":
					tag["description"] = row["tooltip"]
				
				tags[row["name"]] = tag
			
	return types, tags

def buildSchema(row, tagProvider, dtNamespaceUri):
	tpTypes = "[%s]_types_/" % tagProvider
	config = system.tag.getConfiguration(str(row["fullPath"]), True)[0]

	(types, tags) = parseTags(str(row["fullPath"]), config)
	
	schema = {}
	
	if "tooltip" in row and row["tooltip"] != None and row["tooltip"] != "":
		schema["description"] = row["tooltip"]
		
	query = {
	  "options": {
	    "includeUdtMembers": True,
	    "includeUdtDefinitions": True
	  },
	  "condition": {
	    "hierarchy": {
	      "typeId": str(row["fullPath"]),
	      "relationship": "SubType"
	    },
	    "tagType": "UdtType",
	    "attributes": {
	      "values": [],
	      "requireAll": True
	    }
	  }
	}
	
	relatedSchema = {}
	res = system.tag.query(tagProvider, query)
	if len(res):
		if "related" not in relatedSchema:
			relatedSchema["related"] = {}
		
		subTypes = []
		for subType in res:
			subTypes.append(i3x.utils.pathToElementId(str(subType["fullPath"])))
			
		relatedSchema["related"]["InheritedBy"] = subTypes
		
	if "typeId" in row and row["typeId"] != None and row["typeId"] != "":
		if "related" not in relatedSchema:
			relatedSchema["related"] = {}
			
		relatedSchema["related"]["InheritsFrom"] = i3x.utils.pathToElementId("%s%s" % (tpTypes, row["typeId"]))
	
	if len(types):
		if "related" not in relatedSchema:
			relatedSchema["related"] = {}
			
		relatedSchema["related"]["HasComponent"] = types
		
	
	if "related" in relatedSchema and "InheritsFrom" in relatedSchema["related"]:
		# Remove all parent tags
		parentConfig = system.tag.getConfiguration(i3x.utils.elementIdToPath(relatedSchema["related"]["InheritsFrom"]), True)[0]
		parentTags = []
		if "tags" in parentConfig:
			for row in parentConfig["tags"]:
				parentTags.append(row["name"])
		newTags = {}
		for tag in tags:
			if tag not in parentTags:
				newTags[tag] = tags[tag]
		
		schema.update({
			"allOf": [
				{"$ref": "#/types/%s" % relatedSchema["related"]["InheritsFrom"]},
				{
					"type":"object",
					"properties":newTags
				}
			]
		})
	else:
		schema.update({
			"type":"object",
			"properties":tags
		})
	
	if "related" in relatedSchema and "HasComponent" in relatedSchema["related"]:
		schema["related"] = {"relationshipType":"HasComponent", "types":relatedSchema["related"]["HasComponent"]}
	elif "related" in relatedSchema and "InheritsFrom" in relatedSchema["related"]:
		schema["related"] = {"relationshipType":"InheritsFrom", "types":[relatedSchema["related"]["InheritsFrom"]]}
	elif "related" in relatedSchema and "InheritedBy" in relatedSchema["related"]:
		schema["related"] = {"relationshipType":"InheritedBy", "types":relatedSchema["related"]["InheritedBy"]}
		
	if "parameters" in row and row["parameters"] != None and len(row["parameters"]) > 0:
		schema["parameters"] = {}
		for param in row["parameters"]:
			paramValue = row["parameters"][param]
			schema["parameters"][param] = paramValue if isinstance(paramValue, basestring) else paramValue.value
	
	return schema
	
def getTagValue(udtInstance, value):
	if value != None:
		children = i3x.utils.getChildrenObjectNames(udtInstance, "HasComponent")
		objValue = value.value.toDict()
		childrenValues = i3x.utils.removeChildren(objValue, children)
		quality = value.quality.toString()
		timestamp = i3x.utils.formatUtc(value.timestamp)
		return {"value":{"value":objValue, "quality":quality, "timestamp":timestamp}, "childrenValues":childrenValues}
	
	return None