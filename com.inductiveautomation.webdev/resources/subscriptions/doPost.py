def doPost(request, session):
	import traceback
	
	try:
		requestData = request["postData"]
		remainingPath = request["remainingPath"]
		
		callType = "create"
		isBulk = False
		if remainingPath != None and remainingPath != "" and remainingPath.endswith("/register"):
			callType = "register"
			isBulk = True
		elif remainingPath != None and remainingPath != "" and remainingPath.endswith("/unregister"):
			callType = "unregister"
			isBulk = True
		elif remainingPath != None and remainingPath != "" and remainingPath.endswith("/sync"):
			callType = "sync"
		elif remainingPath != None and remainingPath != "" and remainingPath.endswith("/delete"):
			callType = "delete"
			isBulk = True
		elif remainingPath != None and remainingPath != "" and remainingPath.endswith("/list"):
			callType = "list"
			isBulk = True

		(errorCode, bulkError, error, result) = i3x.handlers.getSubscriptions(callType, requestData)
	except:
		errorCode = 500
		bulkError = False
		error = traceback.format_exc()
		result = None
		
	return i3x.handlers.handleResponse(request, errorCode, isBulk, bulkError, error, result)