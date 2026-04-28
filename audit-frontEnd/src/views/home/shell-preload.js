(function() {
    try {
        if (localStorage.getItem("auditNavCollapsed") === "true") {
            document.documentElement.classList.add("nav-collapsed-preload");
        }
    } catch (error) {
        document.documentElement.classList.remove("nav-collapsed-preload");
    }
})();
