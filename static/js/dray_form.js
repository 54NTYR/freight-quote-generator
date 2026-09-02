(function () {
    var cfg = {};
    try {
        cfg = JSON.parse(document.getElementById("dray-form-config").textContent || "{}");
    } catch (err) {
        cfg = {};
    }
    var rates = cfg.rates || {};
    var previousQuotes = cfg.previousQuotes || [];
    var owLimit = Number(cfg.overweightLbs || 44000);
    var prepullMiles = Number(cfg.prepullMiles || 150);

    var form = document.getElementById("quoteForm");
    var direction = document.getElementById("direction");
    var originLabel = document.getElementById("origin_terminal_label");
    var returnLabel = document.getElementById("return_terminal_label");
    var facilityList = document.getElementById("facility_list");
    var validInput = document.getElementById("valid_until");
    var loadWeight = document.getElementById("load_weight_lbs");
    var overweightBox = document.getElementById("overweight");
    var owWarning = document.getElementById("overweight_warning");
    var prepullBox = document.getElementById("prepull");
    var milesWarning = document.getElementById("prepull_miles_warning");
    var fscMode = document.getElementById("fsc_mode");
    var fscLabel = document.getElementById("fsc_value_label");
    var firstLegMiles = null;
    var terminalDraftKey = "jfDrayTerminalDraft:" + window.location.pathname;
    var terminalDraftIds = [
        "origin_terminal", "origin_terminal_id", "origin_zip", "origin_city", "origin_state",
        "return_terminal", "return_terminal_id", "return_zip", "return_city", "return_state"
    ];

    function saveTerminalDraft() {
        var draft = {};
        terminalDraftIds.forEach(function (id) {
            var el = document.getElementById(id);
            if (el) draft[id] = el.value || "";
        });
        try {
            sessionStorage.setItem(terminalDraftKey, JSON.stringify(draft));
        } catch (err) {}
    }

    function restoreTerminalDraft() {
        var draft = null;
        try {
            draft = JSON.parse(sessionStorage.getItem(terminalDraftKey) || "null");
        } catch (err) {
            draft = null;
        }
        if (!draft) return;
        terminalDraftIds.forEach(function (id) {
            var el = document.getElementById(id);
            if (el && typeof draft[id] === "string") el.value = draft[id];
        });
    }

    function money(n) {
        return "$" + (Number(n) || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }

    function esc(value) {
        return String(value || "").replace(/[&<>"']/g, function (ch) {
            return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
        });
    }

    function isOn(el) {
        return !!(el && el.checked);
    }

    function num(id) {
        var el = document.getElementById(id);
        var v = parseFloat(el && el.value);
        return Number.isFinite(v) ? v : 0;
    }

    function directionLabels() {
        var exp = direction && direction.value === "export";
        if (originLabel) originLabel.textContent = exp ? "Empty PU" : "Full OUT";
        if (returnLabel) returnLabel.textContent = exp ? "Full IN" : "Empty IN";
        var role = exp ? "Shipper" : "Receiver";
        document.querySelectorAll(".facility-search-label").forEach(function (lab) {
            lab.textContent = role;
        });
    }

    function syncOverweightWarning() {
        if (!loadWeight || !overweightBox || !owWarning) return;
        var weight = parseFloat(loadWeight.value);
        var overLimit = Number.isFinite(weight) && weight > owLimit;
        owWarning.hidden = !(overLimit && !overweightBox.checked);
    }

    function syncPrepullWarning() {
        if (!milesWarning) return;
        var over = Number.isFinite(firstLegMiles) && firstLegMiles > prepullMiles;
        milesWarning.hidden = !(over && !isOn(prepullBox));
    }

    function syncFscLabel() {
        if (!fscMode || !fscLabel) return;
        fscLabel.textContent = fscMode.value === "percent" ? "Percentage (%)" : "Amount ($)";
    }

    function accessorialTotal() {
        var total = num("tolls");
        if (isOn(document.getElementById("reefer"))) total += Number(rates.reefer || 150);
        if (isOn(overweightBox)) total += Number(rates.ow || 150);
        if (isOn(document.getElementById("hazmat"))) total += Number(rates.hazmat || 150);
        if (isOn(document.getElementById("layover"))) total += Number(rates.layover || 300);
        if (isOn(document.getElementById("stop_off"))) total += Number(rates.stop_off || 125);
        if (isOn(prepullBox)) total += Number(rates.prepull || 150);
        if (isOn(document.getElementById("residential"))) total += Number(rates.residential || 100);
        return total;
    }

    function syncTotals() {
        var lh = num("linehaul");
        var fscVal = num("fsc_value");
        var fsc = (fscMode && fscMode.value === "percent") ? lh * fscVal / 100 : fscVal;
        var acc = accessorialTotal();
        var days = Math.max(parseInt(document.getElementById("chassis_days").value, 10) || 2, Number(rates.chassis_min_days || 2));
        var tri = isOn(overweightBox) || isOn(document.getElementById("triaxle"));
        var rate = tri ? Number(rates.triaxle_day || 100) : Number(rates.chassis_day || 50);
        var chassis = rate * days;
        var splitCount = parseInt(document.getElementById("chassis_split").value, 10) || 0;
        var split = splitCount * Number(rates.chassis_split || 150);
        var total = lh + fsc + acc + chassis + split;
        var live = document.getElementById("live_total");
        if (window.JFLiveTotals) JFLiveTotals.set(total);
        else if (live) live.textContent = money(total);
    }

    function zipOf(el) {
        return ((el && el.value) || "").replace(/\D/g, "").slice(0, 5);
    }

    function collectFacilityZips() {
        return Array.prototype.map.call(document.querySelectorAll(".facility-zip"), zipOf)
            .filter(function (z) { return z.length === 5; });
    }

    var milesTimer = null;
    function scheduleMiles() {
        clearTimeout(milesTimer);
        milesTimer = setTimeout(fetchMiles, 400);
    }

    function fetchMiles() {
        var origin = zipOf(document.getElementById("origin_zip"));
        var ret = zipOf(document.getElementById("return_zip")) || origin;
        var dests = collectFacilityZips();
        if (origin.length !== 5 || !dests.length) {
            firstLegMiles = null;
            syncPrepullWarning();
            return;
        }
        fetch("/api/dray/route_miles", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ origin_zip: origin, facility_zips: dests, return_zip: ret })
        }).then(function (res) { return res.json(); }).then(function (data) {
            firstLegMiles = data && data.success ? Number(data.first_leg_miles) : null;
            syncPrepullWarning();
        }).catch(function () {
            firstLegMiles = null;
            syncPrepullWarning();
        });
    }

    function fetchPlacePredictions(query, done) {
        if (!query) {
            done([]);
            return;
        }
        fetch("/api/places/autocomplete?q=" + encodeURIComponent(query))
            .then(function (res) { return res.json(); })
            .then(function (data) {
                var rows = (data && data.predictions) || [];
                if (!rows.length && data && data.error) {
                    done({ error: data.error === "missing_api_key"
                        ? "Add a Google Maps API key to config.json."
                        : (data.error || "Address search failed.") });
                    return;
                }
                done(rows);
            })
            .catch(function () { done([]); });
    }

    function fetchPlaceDetails(placeId, done) {
        if (!placeId) {
            done(null);
            return;
        }
        fetch("/api/places/details?place_id=" + encodeURIComponent(placeId))
            .then(function (res) { return res.json(); })
            .then(function (data) {
                done(data && data.ok ? data.place : null);
            })
            .catch(function () { done(null); });
    }

    function bindPlacesSearch(input, onPick) {
        if (!input || input.dataset.placesBound === "1") return;
        input.dataset.placesBound = "1";
        var wrap = input.closest(".suggest-wrap") || input.parentElement;
        var list = wrap.querySelector(".suggest-list");
        if (!list) {
            list = document.createElement("div");
            list.className = "suggest-list";
            list.hidden = true;
            wrap.appendChild(list);
        }
        var timer = null;
        function hide() { list.hidden = true; list.innerHTML = ""; }
        function pick(row) {
            hide();
            if (row && (row.zip || row.city || row.address)) {
                onPick({
                    name: row.name || row.primary || "",
                    address: row.address || row.primary || "",
                    city: row.city || "",
                    state: row.state || "",
                    zip: row.zip || ""
                });
                return;
            }
            fetchPlaceDetails(row.placeId, function (parsed) {
                onPick(parsed || {
                    name: row.primary || "",
                    address: row.primary || "",
                    city: "",
                    state: "",
                    zip: ""
                });
            });
        }
        function render(rows) {
            list.innerHTML = "";
            if (rows && rows.error) {
                var err = document.createElement("div");
                err.className = "suggest-powered";
                err.textContent = rows.error;
                list.appendChild(err);
                list.hidden = false;
                return;
            }
            if (!rows || !rows.length) {
                hide();
                return;
            }
            rows.forEach(function (row) {
                var item = document.createElement("button");
                item.type = "button";
                item.className = "suggest-item";
                item.innerHTML = '<span class="suggest-pin" aria-hidden="true"></span>' +
                    "<span><strong>" + esc(row.primary) + "</strong> " +
                    '<span class="suggest-secondary">' + esc(row.secondary || "") + "</span></span>";
                item.addEventListener("mousedown", function (ev) {
                    ev.preventDefault();
                    pick(row);
                });
                list.appendChild(item);
            });
            var foot = document.createElement("div");
            foot.className = "suggest-powered";
            foot.textContent = "powered by Google";
            list.appendChild(foot);
            list.hidden = false;
        }
        input.addEventListener("input", function () {
            var q = (input.value || "").trim();
            clearTimeout(timer);
            if (q.length < 3) {
                hide();
                return;
            }
            timer = setTimeout(function () { fetchPlacePredictions(q, render); }, 180);
        });
        input.addEventListener("blur", function () { setTimeout(hide, 180); });
    }

    function completePlace(parsed) {
        var name = ((parsed && parsed.name) || "").trim();
        var address = ((parsed && parsed.address) || "").trim();
        if (!name) name = address;
        if (!address) address = name;
        return {
            name: name,
            address: address,
            city: ((parsed && parsed.city) || "").trim(),
            state: ((parsed && parsed.state) || "").trim(),
            zip: ((parsed && parsed.zip) || "").trim()
        };
    }

    function bindFacilityPlaces(input, block) {
        bindPlacesSearch(input, function (parsed) {
            var place = completePlace(parsed);
            if (input) input.value = place.name;
            var address = block.querySelector('[name="facility_address"]');
            var city = block.querySelector('[name="facility_city"]');
            var state = block.querySelector('[name="facility_state"]');
            var zip = block.querySelector('[name="facility_zip"]');
            if (address) address.value = place.address;
            if (city) city.value = place.city;
            if (state) state.value = place.state;
            if (zip) zip.value = place.zip;
            scheduleMiles();
            syncTotals();
        });
    }

    function bindAllFacilityPlaces() {
        document.querySelectorAll("[data-facility]").forEach(function (block) {
            bindFacilityPlaces(block.querySelector(".facility-search"), block);
        });
    }

    function bindTerminalPlaces() {
        var name = document.getElementById("new_terminal_name");
        if (!name) return;
        bindPlacesSearch(name, function (parsed) {
            name.value = parsed.name || parsed.address || "";
            document.getElementById("new_terminal_address").value = parsed.address || parsed.name || "";
            document.getElementById("new_terminal_city").value = parsed.city || "";
            document.getElementById("new_terminal_state").value = parsed.state || "";
            document.getElementById("new_terminal_zip").value = parsed.zip || "";
        });
    }

    function bindTotalsDrag(box) {
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

    function terminalLabel(row) {
        var bits = [row.city, row.state, row.zip].filter(Boolean).join(", ");
        return { primary: row.name, secondary: bits };
    }

    function bindTerminalSearch(wrap) {
        var input = wrap.querySelector('input[type="text"]');
        var list = wrap.querySelector(".suggest-list");
        var field = wrap.getAttribute("data-terminal-field");
        var timer = null;
        function hide() { list.hidden = true; list.innerHTML = ""; }
        function pick(row) {
            input.value = row.name || "";
            if (field === "origin") {
                document.getElementById("origin_terminal_id").value = row.id || "";
                document.getElementById("origin_zip").value = row.zip || "";
                document.getElementById("origin_city").value = row.city || "";
                document.getElementById("origin_state").value = row.state || "";
            } else {
                document.getElementById("return_terminal_id").value = row.id || "";
                document.getElementById("return_zip").value = row.zip || "";
                document.getElementById("return_city").value = row.city || "";
                document.getElementById("return_state").value = row.state || "";
            }
            hide();
            scheduleMiles();
            saveTerminalDraft();
        }
        function render(rows) {
            list.innerHTML = "";
            if (!rows.length) {
                hide();
                return;
            }
            rows.forEach(function (row) {
                var item = document.createElement("button");
                item.type = "button";
                item.className = "suggest-item";
                var bits = terminalLabel(row);
                item.innerHTML = '<span class="suggest-pin" aria-hidden="true"></span>' +
                    '<span><strong>' + bits.primary + '</strong> ' +
                    '<span class="suggest-secondary">' + bits.secondary + "</span></span>";
                item.addEventListener("mousedown", function (ev) {
                    ev.preventDefault();
                    pick(row);
                });
                list.appendChild(item);
            });
            list.hidden = false;
        }
        input.addEventListener("input", function () {
            var q = input.value;
            clearTimeout(timer);
            timer = setTimeout(function () {
                fetch("/api/terminals?q=" + encodeURIComponent(q))
                    .then(function (res) { return res.json(); })
                    .then(function (data) { render((data && data.terminals) || []); })
                    .catch(function () { hide(); });
            }, 180);
        });
        input.addEventListener("blur", function () { setTimeout(hide, 180); });
        input.addEventListener("focus", function () {
            if (input.value) input.dispatchEvent(new Event("input"));
        });
    }

    document.querySelectorAll(".suggest-wrap[data-terminal-field]").forEach(bindTerminalSearch);

    function addFacility(values) {
        var block = document.querySelector("[data-facility]").cloneNode(true);
        block.querySelectorAll("input").forEach(function (el) {
            el.value = "";
            delete el.dataset.placesBound;
        });
        block.querySelectorAll(".suggest-list").forEach(function (el) {
            el.hidden = true;
            el.innerHTML = "";
        });
        var search = block.querySelector(".facility-search");
        var searchLabel = block.querySelector(".facility-search-label");
        if (search) {
            search.id = "facility_search_" + Date.now();
            if (searchLabel) searchLabel.setAttribute("for", search.id);
        }
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "text-remove";
        remove.textContent = "Remove facility";
        remove.addEventListener("click", function () {
            block.remove();
            scheduleMiles();
        });
        block.appendChild(remove);
        if (values) fillFacility(block, values);
        facilityList.appendChild(block);
        directionLabels();
        bindFacilityPlaces(block.querySelector(".facility-search"), block);
        return block;
    }

    function fillFacility(block, values) {
        var map = {
            facility_name: values.facility_name || values.name || "",
            facility_address: values.facility_address || values.address || "",
            facility_city: values.facility_city || values.city || "",
            facility_state: values.facility_state || values.state || "",
            facility_zip: values.facility_zip || values.zip || ""
        };
        Object.keys(map).forEach(function (name) {
            var el = block.querySelector('[name="' + name + '"]');
            if (el) el.value = map[name];
        });
        var search = block.querySelector(".facility-search");
        if (search && map.facility_name) search.value = map.facility_name;
    }

    document.getElementById("add_facility_btn").addEventListener("click", function () {
        addFacility();
    });

    var modal = document.getElementById("terminal_modal");
    function openModal() {
        ["new_terminal_name", "new_terminal_address", "new_terminal_city", "new_terminal_state", "new_terminal_zip"]
            .forEach(function (id) { document.getElementById(id).value = ""; });
        document.getElementById("terminal_modal_error").hidden = true;
        modal.hidden = false;
        document.getElementById("new_terminal_name").focus();
    }
    function closeModal() { modal.hidden = true; }

    document.getElementById("add_terminal_btn").addEventListener("click", openModal);
    document.getElementById("cancel_terminal_btn").addEventListener("click", closeModal);
    document.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape" && modal && !modal.hidden) closeModal();
    });
    modal.addEventListener("click", function (ev) {
        if (ev.target === modal) closeModal();
    });

    document.getElementById("save_terminal_btn").addEventListener("click", function () {
        var payload = {
            name: document.getElementById("new_terminal_name").value,
            address: document.getElementById("new_terminal_address").value,
            city: document.getElementById("new_terminal_city").value,
            state: document.getElementById("new_terminal_state").value,
            zip: document.getElementById("new_terminal_zip").value
        };
        var err = document.getElementById("terminal_modal_error");
        fetch("/api/terminals", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }).then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
            .then(function (result) {
                if (!result.ok) {
                    err.textContent = (result.data && result.data.error) || "Could not save terminal.";
                    err.hidden = false;
                    return;
                }
                var rec = result.data.terminal || {};
                document.getElementById("origin_terminal").value = rec.name || payload.name;
                document.getElementById("origin_terminal_id").value = rec.id || "";
                document.getElementById("origin_zip").value = rec.zip || payload.zip;
                document.getElementById("origin_city").value = rec.city || payload.city;
                document.getElementById("origin_state").value = rec.state || payload.state;
                closeModal();
                scheduleMiles();
                saveTerminalDraft();
            }).catch(function () {
                err.textContent = "Could not save terminal.";
                err.hidden = false;
            });
    });

    function asList(value) {
        if (Array.isArray(value)) return value;
        if (value == null || value === "") return [];
        return [value];
    }

    function truthy(value) {
        return String(value || "").toLowerCase() === "on" || String(value || "").toLowerCase() === "yes" || value === true || value === "1";
    }

    function fillForm(fields) {
        if (!fields || !form) return;
        var skip = { facility_name: 1, facility_address: 1, facility_city: 1, facility_state: 1, facility_zip: 1 };
        Object.keys(fields).forEach(function (key) {
            if (skip[key]) return;
            var els = form.querySelectorAll('[name="' + key + '"]');
            if (!els.length) return;
            var val = fields[key];
            els.forEach(function (el) {
                if (el.type === "checkbox") el.checked = truthy(val);
                else el.value = Array.isArray(val) ? (val[0] || "") : (val == null ? "" : val);
            });
        });
        var names = asList(fields.facility_name);
        var addresses = asList(fields.facility_address);
        var cities = asList(fields.facility_city);
        var states = asList(fields.facility_state);
        var zips = asList(fields.facility_zip);
        var count = Math.max(names.length, addresses.length, cities.length, states.length, zips.length, 1);
        while (count > 1) {
            var last = count - 1;
            if ((names[last] || addresses[last] || cities[last] || states[last] || zips[last] || "").toString().trim()) break;
            count -= 1;
        }
        var blocks = facilityList.querySelectorAll("[data-facility]");
        while (blocks.length > 1) {
            blocks[blocks.length - 1].remove();
            blocks = facilityList.querySelectorAll("[data-facility]");
        }
        fillFacility(blocks[0], {
            facility_name: names[0] || "",
            facility_address: addresses[0] || "",
            facility_city: cities[0] || "",
            facility_state: states[0] || "",
            facility_zip: zips[0] || ""
        });
        for (var i = 1; i < count; i += 1) {
            addFacility({
                facility_name: names[i] || "",
                facility_address: addresses[i] || "",
                facility_city: cities[i] || "",
                facility_state: states[i] || "",
                facility_zip: zips[i] || ""
            });
        }
        var customer = document.getElementById("include_customer");
        if (customer) customer.dispatchEvent(new Event("change"));
        directionLabels();
        syncFscLabel();
        syncOverweightWarning();
        syncTotals();
        scheduleMiles();
        saveTerminalDraft();
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
                var match = previousQuotes.filter(function (row) {
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

    if (form) {
        form.addEventListener("submit", function (ev) {
            var origin = document.getElementById("origin_terminal");
            if (origin && !(origin.value || "").trim()) {
                ev.preventDefault();
                origin.setCustomValidity("Choose an origin terminal before generating the quote.");
                origin.reportValidity();
                origin.focus();
                return;
            }
            if (origin) origin.setCustomValidity("");
            saveTerminalDraft();
        });
        var originField = document.getElementById("origin_terminal");
        if (originField) {
            originField.addEventListener("input", function () {
                originField.setCustomValidity("");
                saveTerminalDraft();
            });
        }
        var returnField = document.getElementById("return_terminal");
        if (returnField) {
            returnField.addEventListener("input", saveTerminalDraft);
        }
    }

    if (validInput && !validInput.value) {
        var d = new Date();
        d.setDate(d.getDate() + 7);
        validInput.value = d.toISOString().slice(0, 10);
    }

    if (direction) direction.addEventListener("change", directionLabels);
    directionLabels();
    if (loadWeight) loadWeight.addEventListener("input", function () { syncOverweightWarning(); syncTotals(); });
    if (overweightBox) overweightBox.addEventListener("change", function () { syncOverweightWarning(); syncTotals(); });
    if (prepullBox) prepullBox.addEventListener("change", function () { syncPrepullWarning(); syncTotals(); });
    if (fscMode) fscMode.addEventListener("change", function () { syncFscLabel(); syncTotals(); });
    if (form) {
        form.addEventListener("input", syncTotals);
        form.addEventListener("change", syncTotals);
        form.addEventListener("input", function (ev) {
            if (ev.target && (ev.target.classList.contains("facility-zip") || ev.target.id === "origin_zip" || ev.target.id === "return_zip")) {
                scheduleMiles();
            }
        });
    }
    syncFscLabel();
    syncOverweightWarning();
    syncPrepullWarning();
    syncTotals();
    bindAllFacilityPlaces();
    bindTerminalPlaces();
    bindTotalsDrag(document.getElementById("liveTotals") || document.getElementById("drayLiveTotals"));
    window.addEventListener("pagehide", saveTerminalDraft);
    window.addEventListener("pageshow", function () {
        restoreTerminalDraft();
        setTimeout(restoreTerminalDraft, 0);
        setTimeout(function () {
            restoreTerminalDraft();
            scheduleMiles();
        }, 50);
        directionLabels();
        syncFscLabel();
        syncOverweightWarning();
        syncPrepullWarning();
        syncTotals();
        scheduleMiles();
    });
    restoreTerminalDraft();
})();
