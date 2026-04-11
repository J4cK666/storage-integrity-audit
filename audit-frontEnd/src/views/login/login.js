// 注册按钮功能实现
document.addEventListener('DOMContentLoaded', function() {
    const loginLink = document.getElementById('register-link');
    if (loginLink) {
        loginLink.addEventListener('click', function(event) {
            event.preventDefault();
            window.location.href = '../register/register.html';
        });
    }
});


function test() {
    console.log('test');
}