(function() {
    const protocol = window.location.protocol === "https:" ? "https:" : "http:";
    const hostname = window.location.hostname || "127.0.0.1";
    const backendPort = window.AUDIT_BACKEND_PORT || "8000";
    const explicitBaseUrl = window.AUDIT_API_BASE_URL;

    window.AUDIT_CONFIG = {
        API_BASE_URL: explicitBaseUrl || `${protocol}//${hostname}:${backendPort}`
    };
})();
