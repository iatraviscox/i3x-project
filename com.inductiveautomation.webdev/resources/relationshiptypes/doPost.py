def doPost(request, session):
	import traceback
	
	try:
		requestData = request["postData"]
		elementIds = requestData.get("elementIds", None)
		(errorCode, bulkError, error, result) = i3x.handlers.getRelationshipTypes(None, elementIds)
	except:
		errorCode = 500
		bulkError = False
		error = traceback.format_exc()
		result = None
		
	return i3x.handlers.handleResponse(request, errorCode, True, bulkError, error, result)