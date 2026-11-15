document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".alert").forEach(function (element, index) {
        if (index > 2) {
            element.remove();
        }
    });
});
