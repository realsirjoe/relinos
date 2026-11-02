globalThis.setProxy = async (scheme, host, port) => {
    await chrome.proxy.settings.set({
        value: {
            mode: "fixed_servers",
            rules: {
                singleProxy: {
                    scheme: scheme,
                    host: host,
                    port: port
                }
            }
        },
        scope: "regular"
    });
    return "OK";
};

globalThis.clearProxy = async () => {
    await chrome.proxy.settings.set({
        value: {
            mode: "direct"
        },
        scope: "regular"
    });
    return "OK";
};
