(function (global) {
    function money(n) {
        var v = Number(n);
        if (!Number.isFinite(v)) v = 0;
        return "$" + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }

    function set(n) {
        var el = document.getElementById("live_total");
        if (el) el.textContent = money(n);
    }

    function bindDrag(box) {
        if (!box) return;
        var dragging = false;
        var startX = 0;
        var startY = 0;
        var origLeft = 0;
        var origTop = 0;
        box.addEventListener("pointerdown", function (ev) {
            if (ev.button !== 0) return;
            ev.preventDefault();
            var rect = box.getBoundingClientRect();
            dragging = true;
            startX = ev.clientX;
            startY = ev.clientY;
            origLeft = rect.left;
            origTop = rect.top;
            box.style.left = rect.left + "px";
            box.style.top = rect.top + "px";
            box.style.right = "auto";
            box.style.bottom = "auto";
            box.style.transform = "none";
            box.classList.add("is-dragging");
            box.setPointerCapture(ev.pointerId);
        });
        box.addEventListener("pointermove", function (ev) {
            if (!dragging) return;
            var left = origLeft + (ev.clientX - startX);
            var top = origTop + (ev.clientY - startY);
            left = Math.max(8, Math.min(window.innerWidth - box.offsetWidth - 8, left));
            top = Math.max(8, Math.min(window.innerHeight - box.offsetHeight - 8, top));
            box.style.left = left + "px";
            box.style.top = top + "px";
        });
        function stopDrag() {
            dragging = false;
            box.classList.remove("is-dragging");
        }
        box.addEventListener("pointerup", stopDrag);
        box.addEventListener("pointercancel", stopDrag);
    }

    global.JFLiveTotals = { money: money, set: set, bindDrag: bindDrag };

    function boot() {
        bindDrag(document.getElementById("liveTotals") || document.getElementById("drayLiveTotals"));
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})(window);
