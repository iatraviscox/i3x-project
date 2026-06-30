def doGet(request, session):
	import traceback
	
	try:
		params = request["params"]
		namespaceUri = params.get("namespaceUri", None)
		(errorCode, bulkError, error, result) = i3x.handlers.getRelationshipTypes(namespaceUri)
	except:
		errorCode = 500
		bulkError = False
		error = traceback.format_exc()
		result = None
		
	return i3x.handlers.handleResponse(request, errorCode, False, bulkError, error, result)