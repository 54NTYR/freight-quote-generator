(function () {
    var quotes = [];
    try {
        var dataEl = document.getElementById("previous-quotes-data");
        quotes = JSON.parse((dataEl && dataEl.textContent) || "[]") || [];
    } catch (err) {
        quotes = [];
    }
    if (!Array.isArray(quotes)) quotes = [];

    function truthy(value) {
        if (Array.isArray(value)) value = value[0];
        var text = String(value == null ? "" : value).toLowerCase();
        return text === "on" || text === "yes" || text === "true" || text === "1";
    }

    function fillForm(fields) {
        var form = document.getElementById("quoteForm");
        if (!fields || !form) return;
        Object.keys(fields).forEach(function (key) {
            var els = form.querySelectorAll('[name="' + key + '"]');
            if (!els.length) return;
            var val = fields[key];
            var scalar = Array.isArray(val) ? (val[0] == null ? "" : val[0]) : (val == null ? "" : val);
            els.forEach(function (el, index) {
                var type = (el.type || "").toLowerCase();
                var assigned = Array.isArray(val)
                    ? (val[index] == null ? scalar : val[index])
                    : scalar;
                if (type === "checkbox") {
                    el.checked = truthy(val);
                } else if (type === "radio") {
                    el.checked = String(el.value) === String(scalar);
                } else if (type === "button" || type === "submit" || type === "reset" || type === "file") {
                    return;
                } else if (el.tagName === "SELECT" || el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
                    el.value = assigned == null ? "" : assigned;
                }
            });
        });

        ["include_customer", "equipment", "ltl_compare"].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.dispatchEvent(new Event("change"));
        });

        var milesEl = document.getElementById("manual_miles");
        var distEl = document.getElementById("distance-info");
        if (milesEl && distEl && String(milesEl.value || "").trim()) {
            distEl.textContent = "Distance: " + milesEl.value + " miles";
            distEl.style.display = "block";
        }

        if (typeof updateSummary === "function") {
            updateSummary();
        } else {
            ["pallet_count", "linehaul_cost", "fuel_surcharge"].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.dispatchEvent(new Event("input"));
            });
        }
    }

    var prevBtn = document.getElementById("load_previous_quote_btn");
    var prevList = document.getElementById("load_previous_quote_list");
    var prevWrap = document.querySelector(".header-quote-wrap");
    if (prevBtn && prevList) {
        function closePrev() {
            prevList.hidden = true;
            prevBtn.setAttribute("aria-expanded", "false");
        }
        function openPrev() {
            prevList.hidden = false;
            prevBtn.setAttribute("aria-expanded", "true");
        }
        prevBtn.addEventListener("click", function (ev) {
            ev.stopPropagation();
            if (prevList.hidden) openPrev();
            else closePrev();
        });
        prevList.querySelectorAll("[data-quote]").forEach(function (item) {
            item.addEventListener("click", function () {
                var match = quotes.filter(function (row) {
                    return String(row.quote_number) === String(item.getAttribute("data-quote"));
                })[0];
                if (match) fillForm(match.fields || {});
                prevBtn.textContent = item.textContent || "Select a quote";
                closePrev();
            });
        });
        document.addEventListener("click", function (ev) {
            if (prevWrap && !prevWrap.contains(ev.target)) closePrev();
        });
        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") closePrev();
        });
    }
})();
