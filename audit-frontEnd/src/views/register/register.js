document.addEventListener('DOMContentLoaded', function() {
    const loginLink = document.getElementById('login-link');
    if (loginLink) {
        loginLink.addEventListener('click', function(event) {
            event.preventDefault();
            window.location.href = '../login/login.html';
        });
    }
});