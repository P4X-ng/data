chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
	if (request.type === 'getLocalizedMessage' && request.key) {
		const localizedMessage = chrome.i18n.getMessage(request.key);
		sendResponse({message: localizedMessage});
	}
});