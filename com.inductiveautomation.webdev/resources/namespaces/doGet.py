def doGet(request, session):
	import traceback
	
	try:
		(errorCode, bulkError, error, result) = i3x.handlers.getNamespaces()
	except:
		errorCode = 500
		bulkError = False
		error = traceback.format_exc()
		result = None
		
	return i3x.handlers.handleResponse(request, errorCode, False, bulkError, error, result)