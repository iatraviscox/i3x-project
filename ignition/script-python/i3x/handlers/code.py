# i3x.handlers
# ------------
# Request handlers for the i3X API. The WebDev endpoint resources are thin
# wrappers (doGet/doPost) that delegate here; this module turns Ignition data
# into i3X response payloads and owns the response envelope.
#
# Each handler returns a 4-tuple consumed by handleResponse():
#     (statusCode, bulkError, errorMessage, result)
#   - statusCode:    HTTP status to send (200/206 carry a body; others are errors)
#   - bulkError:     True if any item in a bulk response failed (sets success=false)
#   - errorMessage:  detail string for error responses (ignored on 2xx)
#   - result:        the payload (a list for bulk endpoints, an object otherwise)

SPEC_VERSION = "1.0"

def handleResponse(request, errorCode, isBulk, bulkError, error, result):
	# Serialize a handler's (code, bulkError, error, result) tuple into the i3X
	# response envelope and send it (gzipped when the client asks for it).
	resp = request["servletResponse"]
	resp.setStatus(errorCode)

	# 2xx (200 OK, 206 Partial Content) carry the success/result envelope.
	if 200 <= errorCode < 300:
		ret = {
			"success": not bulkError,
			"results" if isBulk else "result": result
		}
	else:
		# Everything else uses the spec ErrorResponse {success:false, responseDetail}.
		ret = {
			"success": False,
			"responseDetail": i3x.utils.errorDetail(errorCode, error)
		}

	return _respond(request, system.util.jsonEncode(ret))

def _respond(request, jsonStr):
	# Send the JSON body, honoring Accept-Encoding: gzip per the spec.
	# This runs outside the handler try/except, so any failure must fall back to
	# an uncompressed response rather than surfacing as a 500.
	try:
		servletRequest = request.get("servletRequest", None)
		acceptEncoding = servletRequest.getHeader("Accept-Encoding") if servletRequest is not None else None
		if acceptEncoding is not None and "gzip" in str(acceptEncoding).lower():
			from java.lang import String
			from java.io import ByteArrayOutputStream
			from java.util.zip import GZIPOutputStream
			baos = ByteArrayOutputStream()
			gz = GZIPOutputStream(baos)
			gz.write(String(jsonStr).getBytes("UTF-8"))
			gz.close()
			# Returning a byte[] under 'response' makes WebDev base64-encode it,
			# so write the raw gzip bytes straight to the servlet stream instead.
			resp = request["servletResponse"]
			resp.setHeader("Content-Encoding", "gzip")
			resp.setContentType("application/json")
			out = resp.getOutputStream()
			out.write(baos.toByteArray())
			out.flush()
			return None
	except:
		system.util.getLogger("i3x").warn("gzip encoding failed; sending uncompressed response")

	return {'json': jsonStr}

def serverError(loggerName):
	# Build a generic 500 tuple after logging the real traceback server-side, so
	# internal details (paths, stack frames) never leak to the client.
	import traceback
	system.util.getLogger(loggerName).error(traceback.format_exc())
	return (500, False, "Internal server error", None)

def bulkOk(result, elementId=None, subscriptionId=None):
	# Build a successful BulkResultItem. elementId/subscriptionId are included
	# only when relevant to the endpoint (both are optional in the spec).
	item = {"success": True, "result": result}
	if elementId is not None:
		item["elementId"] = elementId
	if subscriptionId is not None:
		item["subscriptionId"] = subscriptionId
	return item

def bulkErr(status, detail, elementId=None, subscriptionId=None):
	# Build a failed BulkResultItem carrying a spec ErrorDetail under responseDetail.
	item = {"success": False, "result": None, "responseDetail": i3x.utils.errorDetail(status, detail)}
	if elementId is not None:
		item["elementId"] = elementId
	if subscriptionId is not None:
		item["subscriptionId"] = subscriptionId
	return item

def getInfo():
	# GET /info: server version and capability matrix. Public health check.
	# Capabilities reflect what is actually implemented; writes and SSE streaming
	# are not supported, so they are advertised as false.
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
	# GET /relationshiptypes (namespaceUri=None) lists all relationship types;
	# POST /relationshiptypes/query (elementIds set) returns them in bulk form.
	# The i3X relationship types are a fixed, hard-coded set; each declares the
	# elementId of its inverse via reverseOf.
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

	ret = []
	bulkError = False

	if elementIds == None:
		# List form, optionally filtered by namespace.
		for relationship in relationships:
			obj = relationships[relationship]
			if namespaceUri == None or namespaceUri == obj["namespaceUri"]:
				ret.append(obj)
	else:
		# Bulk form: one result item per requested id, in request order.
		for elementId in elementIds:
			if elementId != None:
				if elementId in relationships:
					ret.append(bulkOk(relationships[elementId], elementId=elementId))
				else:
					bulkError = True
					ret.append(bulkErr(404, "Relationship type not found: %s" % elementId, elementId=elementId))

	return (200, bulkError, None, ret)

def getNamespaces():
	# GET /namespaces: the distinct namespace URIs declared by UDT definitions
	# (via the NamespaceUri parameter), plus the OPC-UA core namespace. The
	# displayName is derived from the URI path for readability.
	import urlparse

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

	# The OPC-UA core namespace backs the built-in folder type; always expose it.
	if not coreUAFound:
		ret.append({"uri":i3x.ignition.UaCoreUri, "displayName":"UA"})

	return (200, False, None, ret)

def getObjectTypes(namespaceUri=None, elementIds=None):
	# GET /objecttypes (namespaceUri filter) / POST /objecttypes/query (elementIds).
	# Returns the JSON-Schema definition for each type: the three built-in types
	# (folder, tag provider, alarm) plus every UDT definition across all providers.

	# The three built-in (non-UDT) types, registered under literal elementIds.
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

	from collections import OrderedDict

	bulkError = False

	# Build (and briefly cache) the full type map keyed by elementId: the three
	# built-in types plus every UDT definition across all providers. Serving
	# from this map lets bulk queries preserve request order and report unknown
	# ids as per-item 404s without decoding caller-supplied strings.
	allTypes = i3x.utils.cacheGet("objectTypes")
	if allTypes is None:
		allTypes = OrderedDict()
		allTypes["folder-type"] = folderObj
		allTypes["ignition-tag-provider"] = tagProviderObj
		allTypes["ignition-alarm"] = alarmObj
		for tagProvider in i3x.ignition.getTagProviders():
			for row in i3x.ignition.getUdtDefs(tagProvider):
				dtNamespaceUri = i3x.utils.getNamespaceUriParam(row)
				dtElementId = i3x.utils.pathToElementId(str(row["fullPath"]))
				allTypes[dtElementId] = {"elementId":dtElementId, "displayName":row["name"], "namespaceUri":dtNamespaceUri, "sourceTypeId":dtElementId, "version":"1.0.0", "schema":i3x.ignition.buildSchema(row, tagProvider, dtNamespaceUri)}
		i3x.utils.cacheSet("objectTypes", allTypes)

	if elementIds is not None:
		# Bulk: preserve request order, per-item 404 for unknown ids.
		ret = []
		for elementId in elementIds:
			if elementId in allTypes:
				ret.append(bulkOk(allTypes[elementId], elementId=elementId))
			else:
				bulkError = True
				ret.append(bulkErr(404, "Object type not found: %s" % elementId, elementId=elementId))
		return (200, bulkError, None, ret)

	# Non-bulk: optionally filter by namespace.
	ret = [obj for obj in allTypes.values() if namespaceUri == None or obj["namespaceUri"] == namespaceUri]
	return (200, False, None, ret)

def getObjects(typeId=None, includeMetadata=False, root=None, elementIds=None, callType="list", relationshipType=None, maxDepth=1, startTime=None, endTime=None):
	# Backs every Object endpoint, dispatched by callType:
	#   list    - GET /objects and POST /objects/list
	#   related - POST /objects/related
	#   value   - POST /objects/value      (live values, recursed to maxDepth)
	#   history - POST /objects/history    (historian values, recursed to maxDepth)
	# A None elementIds means the non-bulk GET /objects listing; otherwise this is
	# a bulk request keyed by elementId.
	log = system.util.getLogger("i3x.objects")

	bulkError = False

	# Parse the history time range once, up front - not inside the per-element
	# loop (re-parsing an already-parsed Date would throw on the 2nd element).
	startDate = None
	endDate = None
	if callType == "history":
		if startTime == None or endTime == None:
			return (400, False, "startTime and endTime are required (RFC 3339)", None)
		try:
			startDate = i3x.utils.parseUtc(startTime)
			endDate = i3x.utils.parseUtc(endTime)
		except:
			return (400, False, "startTime and endTime must be RFC 3339 timestamps", None)

	if typeId != None:
		typeId = i3x.utils.elementIdToPath(typeId)

	udtInstances = i3x.ignition.getUdtInstances()

	isBulk = elementIds != None
	ret = []

	if not isBulk:
		# GET /objects: list every addressable object, optionally filtered by type
		# or restricted to roots. Intermediate folders nested under a UDT are not
		# objects in their own right and are skipped.
		for udtInstancePath in udtInstances:
			udtInstance = udtInstances[udtInstancePath]
			dtTypeId = udtInstance["typeId"]

			if typeId == None or typeId == dtTypeId:
				if udtInstance["type"] == "folder" and udtInstance["parentUdt"] != None:
					continue

				if root and udtInstance["parentId"] != None:
					continue

				ret.append(i3x.utils.buildUdtInstanceObj(udtInstance, includeMetadata))
	else:
		# Bulk: index instances by elementId so each requested id is a direct
		# lookup instead of a full scan of every instance per id.
		byElementId = {}
		for path in udtInstances:
			byElementId[udtInstances[path]["elementId"]] = udtInstances[path]

		for elementId in elementIds:
			udtInstance = byElementId.get(elementId, None)

			# Intermediate folders nested under a UDT aren't addressable objects;
			# treat them (and unknown ids) as not found.
			if udtInstance is None or (udtInstance["type"] == "folder" and udtInstance["parentUdt"] != None):
				bulkError = True
				ret.append(bulkErr(404, "Element not found: %s" % elementId, elementId=elementId))
				continue

			udtInstancePath = udtInstance["path"]
			obj = i3x.utils.buildUdtInstanceObj(udtInstance, includeMetadata)

			if callType == "related":
				# Return the objects reachable from this one across every edge type
				# (optionally filtered by relationshipType inside getRelatedObjects).
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
					# An alarm's "value" is its current alarm status object.
					alarmObj = udtInstance["alarmObj"]
					quality = "Good"
					timestamp = alarmObj["eventTime"]
					elementObj = {"value":udtInstance["alarmObj"], "quality":quality, "timestamp":timestamp, "isComposition":False}
				elif udtInstance["typeId"] != "folder-type" and udtInstance["typeId"] != "ignition-tag-provider":
					# Read the live UDT value, then recurse into composition children
					# up to maxDepth, attaching them under "components".
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
					# Alarm history needs an alarm journal profile. If none is
					# configured (or the query fails), return empty history
					# rather than failing the whole request with a 500.
					try:
						res = system.alarm.queryJournal(startDate, endDate, journalName=i3x.ignition.ALARM_JOURNAL, source=udtInstancePath)
						for row in res:
							alarmObj = i3x.ignition.getAlarmObj(row)
							elementObj["values"].append({"value":alarmObj, "quality":"Good", "timestamp":alarmObj["eventTime"], "isComposition":False})
					except:
						log.warn("Alarm journal query failed for %s; returning empty history" % elementId)
				elif udtInstance["typeId"] != "folder-type" and udtInstance["typeId"] != "ignition-tag-provider":
					# Collect the historizable leaf tags (recursing to maxDepth),
					# query the historian for all of them at once, then de-duplicate
					# consecutive identical rows before shaping the response.
					tagConfig = system.tag.getConfiguration(udtInstancePath, True)
					if len(tagConfig) and "tags" in tagConfig[0]:
						objs = {"tags":[], "objects":{}}
						tags = i3x.utils.getTags(udtInstancePath, objs, tagConfig[0]["tags"], 1, maxDepth)
						if len(tags):
							minutes = system.date.minutesBetween(startDate, endDate)
							res = system.historian.queryAggregatedPoints(paths=tags, startTime=startDate, endTime=endDate, aggregates=["LastValue"] * len(tags), fillModes=["PREV"] * len(tags), returnFormat="WIDE", returnSize=max(1, minutes), includeBounds=True)
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

								# Keep only rows that changed and aren't entirely null.
								if rowValues != prevValues and not allNull:
									prevValues = dict(rowValues)
									rowValues["t_stamp"] = timestamp
									historyValues.append(rowValues)

							i3x.utils.addChildrenHistory(elementObj, objs, historyValues)

				ret.append(bulkOk(elementObj, elementId=elementId))
			else:
				# callType == "list": just the object record.
				ret.append(bulkOk(obj, elementId=elementId))

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
	# Tear down every listener created for a monitored item and forget it.
	for (tagPath, udtInstance, listener) in subscription["listeners"].get(elementId, []):
		i3x.tag.unsubscribe(tagPath, udtInstance, listener)
	if elementId in subscription["listeners"]:
		del subscription["listeners"][elementId]
	if elementId in subscription["monitoredItems"]:
		del subscription["monitoredItems"][elementId]

def getSubscriptions(callType, requestData=None):
	# Backs every /subscriptions endpoint, dispatched by callType
	# (create/list/delete/register/unregister/sync). Subscriptions are scoped to
	# a clientId so one client can never see or mutate another's subscriptions.
	log = system.util.getLogger("i3x.subscriptions")

	bulkError = False

	clientId = requestData.get("clientId", None)
	if clientId is None:
		return (400, False, "clientId is required", None)

	subscriptionIds = i3x.utils.getSubscriptions(clientId)
	if callType == "list":
		# Report each requested subscription's monitored items, or a 404 per id.
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
					# are cleaned up rather than leaked (registration is idempotent).
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
		# Acknowledge prior batches and return all pending ones. Staged updates
		# (appended by tag-change listeners) are bundled into a new batch here.
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
