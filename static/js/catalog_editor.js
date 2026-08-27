(function (window) {
    "use strict";

    function readData() {
        var node = document.getElementById("catalog-data");
        if (!node) return [];
        try {
            return JSON.parse(node.textContent || "[]");
        } catch (err) {
            return [];
        }
    }

    function esc(value) {
        return String(value || "").replace(/[&<>"']/g, function (ch) {
            return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
        });
    }

    function showError(id, message) {
        var el = document.getElementById(id);
        if (!el) return;
        if (message) {
            el.textContent = message;
            el.hidden = false;
        } else {
            el.textContent = "";
            el.hidden = true;
        }
    }

    function showStatus(message) {
        var el = document.getElementById("catalog_status");
        if (!el) return;
        if (!message) {
            el.hidden = true;
            el.textContent = "";
            return;
        }
        el.textContent = message;
        el.hidden = false;
    }

    function jsonFetch(url, options) {
        return fetch(url, options).then(function (res) {
            return res.json().then(function (body) {
                return { ok: res.ok, status: res.status, body: body || {} };
            }).catch(function () {
                return { ok: res.ok, status: res.status, body: {} };
            });
        });
    }

    function upsertRow(rows, rec) {
        var existing = rows.filter(function (item) { return item.id === rec.id; })[0];
        if (existing) {
            Object.keys(rec).forEach(function (key) { existing[key] = rec[key]; });
            return;
        }
        rows.push(rec);
        rows.sort(function (a, b) { return a.name.toLowerCase().localeCompare(b.name.toLowerCase()); });
    }

    function bindPlacesSearch(input, onPick) {
        if (!input || input.dataset.placesBound === "1") return;
        input.dataset.placesBound = "1";
        var wrap = input.closest(".suggest-wrap") || input.parentElement;
        var list = wrap && wrap.querySelector(".suggest-list");
        if (!list) {
            list = document.createElement("div");
            list.className = "suggest-list";
            list.hidden = true;
            wrap.appendChild(list);
        }
        var timer = null;
        function hide() {
            list.hidden = true;
            list.innerHTML = "";
        }
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
            if (!row || !row.placeId) {
                onPick({
                    name: (row && (row.name || row.primary)) || "",
                    address: (row && (row.address || row.primary)) || "",
                    city: "",
                    state: "",
                    zip: ""
                });
                return;
            }
            fetch("/api/places/details?place_id=" + encodeURIComponent(row.placeId))
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    onPick((data && data.ok && data.place) || {
                        name: row.primary || "",
                        address: row.primary || "",
                        city: "",
                        state: "",
                        zip: ""
                    });
                })
                .catch(function () {
                    onPick({
                        name: row.primary || "",
                        address: row.primary || "",
                        city: "",
                        state: "",
                        zip: ""
                    });
                });
        }
        function render(payload) {
            list.innerHTML = "";
            var rows = (payload && payload.predictions) || payload;
            if (payload && payload.error && (!rows || !rows.length)) {
                var err = document.createElement("div");
                err.className = "suggest-powered";
                err.textContent = payload.error;
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
            timer = setTimeout(function () {
                fetch("/api/places/autocomplete?q=" + encodeURIComponent(q))
                    .then(function (res) { return res.json(); })
                    .then(render)
                    .catch(hide);
            }, 180);
        });
        input.addEventListener("blur", function () { setTimeout(hide, 180); });
    }

    function applyPlace(prefix, parsed) {
        var name = document.getElementById(prefix + "_name");
        var address = document.getElementById(prefix + "_address");
        var city = document.getElementById(prefix + "_city");
        var state = document.getElementById(prefix + "_state");
        var zip = document.getElementById(prefix + "_zip");
        if (name) name.value = parsed.name || parsed.address || "";
        if (address) address.value = parsed.address || parsed.name || "";
        if (city) city.value = parsed.city || "";
        if (state) state.value = parsed.state || "";
        if (zip) zip.value = parsed.zip || "";
    }

    function bindLocalSuggest(input, getRows, describe, onPick) {
        if (!input) return;
        var wrap = input.closest(".suggest-wrap") || input.parentElement;
        var list = wrap && wrap.querySelector(".suggest-list");
        if (!list) return;
        function hide() {
            list.hidden = true;
            list.innerHTML = "";
        }
        function matches(row, needle) {
            if (!needle) return true;
            return describe(row).blob.toLowerCase().indexOf(needle) !== -1;
        }
        function render() {
            var needle = (input.value || "").trim().toLowerCase();
            var hits = getRows().filter(function (row) { return matches(row, needle); });
            list.innerHTML = "";
            if (!hits.length) {
                hide();
                return;
            }
            hits.forEach(function (row) {
                var bits = describe(row);
                var item = document.createElement("button");
                item.type = "button";
                item.className = "suggest-item";
                item.innerHTML = '<span class="suggest-pin" aria-hidden="true"></span>' +
                    "<span><strong>" + esc(bits.primary) + "</strong> " +
                    '<span class="suggest-secondary">' + esc(bits.secondary || "") + "</span></span>";
                item.addEventListener("mousedown", function (ev) {
                    ev.preventDefault();
                    input.value = bits.primary;
                    hide();
                    onPick(row);
                });
                list.appendChild(item);
            });
            list.hidden = false;
        }
        input.addEventListener("input", render);
        input.addEventListener("focus", render);
        input.addEventListener("blur", function () { setTimeout(hide, 180); });
    }

    function setEditorMode(isUpdate, addLabel, updateLabel) {
        var btn = document.getElementById("catalog_add_btn");
        var title = document.getElementById("catalog_form_title");
        var label = isUpdate ? updateLabel : addLabel;
        if (btn) btn.textContent = label;
        if (title) title.textContent = label;
    }

    function initCustomers() {
        var rows = readData();
        var selectedId = null;
        var name = document.getElementById("new_customer_name");
        var email = document.getElementById("new_customer_email");
        var filter = document.getElementById("catalog_filter");

        function clearForm() {
            selectedId = null;
            name.value = "";
            email.value = "";
            if (filter) filter.value = "";
            setEditorMode(false, "Add customer", "Update customer");
        }

        function fillForm(row) {
            selectedId = row.id;
            name.value = row.name || "";
            email.value = row.email || "";
            setEditorMode(true, "Add customer", "Update customer");
        }

        bindLocalSuggest(filter, function () { return rows; }, function (row) {
            return {
                primary: row.name,
                secondary: row.email || "",
                blob: [row.name, row.email].join(" ")
            };
        }, fillForm);

        document.getElementById("catalog_add_btn").addEventListener("click", function () {
            var payload = { name: name.value.trim(), email: email.value.trim() };
            var url = selectedId ? "/api/customers/" + encodeURIComponent(selectedId) : "/api/customers";
            jsonFetch(url, {
                method: selectedId ? "PUT" : "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            }).then(function (res) {
                if (!res.ok) {
                    showError("catalog_add_error", (res.body && res.body.error) || "Customer name is required.");
                    return;
                }
                showError("catalog_add_error", "");
                var rec = res.body.customer;
                upsertRow(rows, rec);
                showStatus("Saved " + rec.name + ".");
                if (selectedId) {
                    fillForm(rec);
                } else {
                    clearForm();
                }
            });
        });
        setEditorMode(false, "Add customer", "Update customer");
    }

    function initLocations() {
        var rows = readData();
        var selectedId = null;
        var filter = document.getElementById("catalog_filter");
        var keys = ["name", "address", "city", "state", "zip"];

        bindPlacesSearch(document.getElementById("new_location_name"), function (parsed) {
            applyPlace("new_location", parsed);
        });

        function clearForm() {
            selectedId = null;
            keys.forEach(function (key) {
                document.getElementById("new_location_" + key).value = "";
            });
            if (filter) filter.value = "";
            setEditorMode(false, "Add location", "Update location");
        }

        function fillForm(row) {
            selectedId = row.id;
            keys.forEach(function (key) {
                document.getElementById("new_location_" + key).value = row[key] || "";
            });
            setEditorMode(true, "Add location", "Update location");
        }

        bindLocalSuggest(filter, function () { return rows; }, function (row) {
            var secondary = [row.address, [row.city, row.state, row.zip].filter(Boolean).join(", ")].filter(Boolean).join(" ");
            return {
                primary: row.name,
                secondary: secondary,
                blob: [row.name, row.address, row.city, row.state, row.zip].join(" ")
            };
        }, fillForm);

        document.getElementById("catalog_add_btn").addEventListener("click", function () {
            var payload = {};
            keys.forEach(function (key) {
                payload[key] = document.getElementById("new_location_" + key).value.trim();
            });
            var url = selectedId ? "/api/terminals/" + encodeURIComponent(selectedId) : "/api/terminals";
            jsonFetch(url, {
                method: selectedId ? "PUT" : "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            }).then(function (res) {
                if (!res.ok) {
                    showError("catalog_add_error", (res.body && res.body.error) || "Terminal name is required.");
                    return;
                }
                showError("catalog_add_error", "");
                var rec = res.body.terminal;
                upsertRow(rows, rec);
                showStatus("Saved " + rec.name + ".");
                if (selectedId) {
                    fillForm(rec);
                } else {
                    clearForm();
                }
            });
        });
        setEditorMode(false, "Add location", "Update location");
    }

    window.CatalogEditor = {
        initCustomers: initCustomers,
        initLocations: initLocations
    };
})(window);
