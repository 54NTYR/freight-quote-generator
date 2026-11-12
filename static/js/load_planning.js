(function () {
    var libraryContainers = [];
    var libraryProducts = [];
    var STOCK_COLORS = [
        "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
        "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
        "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
        "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9"
    ];
    var previewPayload = null;
    var previewResult = null;
    var ORIENT_NAMES = ["upright", "yaw90", "side", "side_turn", "end", "end_turn"];

    function fields(row, name) {
        return row.querySelectorAll('[data-field="' + name + '"]');
    }

    function field(row, name) {
        return row.querySelector('[data-field="' + name + '"]');
    }

    function read(row, name) {
        var nodes = fields(row, name);
        if (!nodes.length) return "";
        if (nodes[0].type === "radio") {
            for (var index = 0; index < nodes.length; index++) {
                if (nodes[index].checked) return nodes[index].value;
            }
            return "";
        }
        var el = nodes[0];
        if (el.type === "checkbox") return !!el.checked;
        return el.value;
    }

    function write(row, name, value) {
        var nodes = fields(row, name);
        if (!nodes.length) return;
        if (nodes[0].type === "radio") {
            var chosen = value == null ? "" : String(value);
            Array.prototype.forEach.call(nodes, function (el) {
                el.checked = el.value === chosen;
            });
            return;
        }
        var el = nodes[0];
        if (el.type === "checkbox") {
            el.checked = !!value;
            return;
        }
        el.value = value == null ? "" : value;
    }

    function syncProductOptions(row) {
        var shape = read(row, "shape") || "box";
        var cylinder = shape === "cylinder";
        row.querySelectorAll("[data-shape-extra]").forEach(function (el) {
            el.hidden = el.getAttribute("data-shape-extra") !== shape;
        });
        row.querySelectorAll("[data-box-size]").forEach(function (el) {
            el.hidden = cylinder;
        });
        row.querySelectorAll("[data-cylinder-size]").forEach(function (el) {
            el.hidden = !cylinder;
        });
        row.querySelectorAll("[data-cylinder-hide]").forEach(function (el) {
            el.hidden = cylinder;
        });
        row.querySelectorAll("[data-cylinder-show]").forEach(function (el) {
            el.hidden = !cylinder;
        });
        if (!cylinder && read(row, "orient_mode") === "standing") write(row, "orient_mode", "all_six");
        row.querySelectorAll("[data-orient-copy]").forEach(function (el) {
            el.textContent = el.getAttribute(cylinder ? "data-cylinder" : "data-box") || el.textContent;
        });
        var boxHelp = row.querySelector("[data-orient-box]");
        var cylinderHelp = row.querySelector("[data-orient-cylinder]");
        if (boxHelp) boxHelp.hidden = cylinder;
        if (cylinderHelp) cylinderHelp.hidden = !cylinder;
        var lengthLabel = row.querySelector("[data-length-label]");
        if (lengthLabel) lengthLabel.textContent = cylinder ? "Length (in)" : "Length (in, back to front)";
        if (cylinder && !read(row, "diameter_in")) {
            var width = read(row, "width_in");
            var height = read(row, "height_in");
            if (width && (!height || width === height)) write(row, "diameter_in", width);
            else if (height && !width) write(row, "diameter_in", height);
        }
        if (!cylinder && read(row, "diameter_in")) {
            if (!read(row, "width_in")) write(row, "width_in", read(row, "diameter_in"));
            if (!read(row, "height_in")) write(row, "height_in", read(row, "diameter_in"));
        }
        var custom = row.querySelector("[data-orient-custom]");
        if (custom) custom.hidden = read(row, "orient_mode") !== "custom";
    }

    function pieceVolume(length, width, height, shape, diameter) {
        if (shape === "cylinder") {
            var radius = asNumber(diameter) / 2;
            return Math.PI * radius * radius * asNumber(length);
        }
        return asNumber(length) * asNumber(width) * asNumber(height);
    }

    function fill(row, data) {
        Object.keys(data || {}).forEach(function (key) {
            if (field(row, key)) write(row, key, data[key]);
        });
    }

    function showMessage(text, ok) {
        var el = document.getElementById("lpError");
        if (!el) return;
        el.hidden = !text;
        el.textContent = text || "";
        el.classList.toggle("lp-ok", !!ok);
    }

    function numberOrBlank(value) {
        if (value == null || String(value).trim() === "") return "";
        return value;
    }

    function collectContainers() {
        return Array.prototype.map.call(document.querySelectorAll("#containerRows .lp-line"), function (row) {
            return {
                container_id: read(row, "container_id"),
                label: read(row, "label"),
                type: read(row, "type"),
                available: read(row, "available"),
                length_in: read(row, "length_in"),
                width_in: read(row, "width_in"),
                height_in: read(row, "height_in"),
                max_payload_lb: read(row, "max_payload_lb"),
                load_direction: read(row, "load_direction")
            };
        });
    }

    function collectLines() {
        return Array.prototype.map.call(document.querySelectorAll("#productRows .lp-line"), function (row) {
            var shape = read(row, "shape") || "box";
            var diameter = read(row, "diameter_in");
            var width = shape === "cylinder" ? diameter : read(row, "width_in");
            var height = shape === "cylinder" ? diameter : read(row, "height_in");
            return {
                product_id: read(row, "product_id"),
                name: read(row, "name"),
                length_in: read(row, "length_in"),
                width_in: width,
                height_in: height,
                diameter_in: shape === "cylinder" ? diameter : "",
                weight_lb: read(row, "weight_lb"),
                qty: read(row, "qty"),
                shape: read(row, "shape") || "box",
                orient_mode: read(row, "orient_mode") || "all_six",
                allowed_orientations: (shape === "cylinder" ? ["upright", "yaw90", "end"] : ORIENT_NAMES).filter(function (name) {
                    return read(row, "allow_" + name);
                }),
                back_depth: numberOrBlank(read(row, "back_depth")),
                seat_height: numberOrBlank(read(row, "seat_height")),
                stem_width: numberOrBlank(read(row, "stem_width")),
                bar_depth: numberOrBlank(read(row, "bar_depth")),
                stackable: read(row, "stackable"),
                on_floor_only: read(row, "on_floor_only"),
                on_top_only: read(row, "on_top_only"),
                max_stack: numberOrBlank(read(row, "max_stack")),
                supported_weight_lb: numberOrBlank(read(row, "supported_weight_lb")),
                stack_index: numberOrBlank(read(row, "stack_index")),
                notes: read(row, "notes"),
                plan_text: read(row, "plan_text"),
                color: read(row, "color")
            };
        });
    }

    function payload() {
        var include = document.getElementById("include_customer");
        return {
            include_customer: !!(include && include.checked),
            customer_name: (document.getElementById("customer_name") || {}).value || "",
            contact_email: (document.getElementById("contact_email") || {}).value || "",
            notes: (document.getElementById("plan_notes") || {}).value || "",
            containers: collectContainers(),
            lines: collectLines()
        };
    }

    function asNumber(value) {
        var number = parseFloat(value);
        return isFinite(number) ? number : 0;
    }

    function halfSize(value) {
        var number = asNumber(value);
        if (number <= 0) return "";
        return Math.round(number * 5) / 10;
    }

    function fillShapeDefaults(row) {
        var shape = read(row, "shape") || "box";
        if (shape === "l_shape") {
            if (!read(row, "back_depth")) write(row, "back_depth", halfSize(read(row, "width_in")));
            if (!read(row, "seat_height")) write(row, "seat_height", halfSize(read(row, "height_in")));
        }
        if (shape === "t_shape") {
            if (!read(row, "stem_width")) write(row, "stem_width", halfSize(read(row, "width_in")));
            if (!read(row, "bar_depth")) write(row, "bar_depth", halfSize(read(row, "length_in")));
        }
    }

    function updateLive() {
        var cubeEl = document.getElementById("lpCube");
        var weightEl = document.getElementById("lpWeight");
        var fitEl = document.getElementById("lpFit");
        if (!cubeEl || !weightEl || !fitEl) return;
        var orderedVolume = 0;
        var orderedWeight = 0;
        var capacityVolume = 0;
        var capacityWeight = 0;
        collectLines().forEach(function (line) {
            var qty = asNumber(line.qty);
            orderedVolume += pieceVolume(line.length_in, line.width_in, line.height_in, line.shape, line.diameter_in) * qty;
            orderedWeight += asNumber(line.weight_lb) * qty;
        });
        collectContainers().forEach(function (box) {
            var count = asNumber(box.available);
            capacityVolume += asNumber(box.length_in) * asNumber(box.width_in) * asNumber(box.height_in) * count;
            capacityWeight += asNumber(box.max_payload_lb) * count;
        });
        cubeEl.textContent = capacityVolume > 0
            ? "Cube " + (Math.round(orderedVolume / capacityVolume * 1000) / 10) + "%"
            : "Cube n/a";
        weightEl.textContent = capacityWeight > 0
            ? "Weight " + (Math.round(orderedWeight / capacityWeight * 1000) / 10) + "%"
            : "Weight n/a";
        document.querySelectorAll("#productRows .lp-line").forEach(function (row) {
            fillShapeDefaults(row);
            var volume = row.querySelector("[data-volume]");
            if (!volume) return;
            var cubic = pieceVolume(
                read(row, "length_in"),
                read(row, "width_in"),
                read(row, "height_in"),
                read(row, "shape") || "box",
                read(row, "diameter_in")
            );
            volume.value = cubic > 0
                ? (Math.round(cubic * 10) / 10) + " cu in (" + (Math.round(cubic / 1728 * 10) / 10) + " cu ft)"
                : "";
        });
        markPreviewStale();
        refreshFit(orderedVolume, orderedWeight, capacityVolume, capacityWeight);
    }

    function refreshFit(orderedVolume, orderedWeight, capacityVolume, capacityWeight) {
        var fitEl = document.getElementById("lpFit");
        if (!fitEl) return;
        var stale = document.getElementById("lpStale");
        var previewIsStale = stale && !stale.hidden;
        if (previewResult && !previewIsStale) {
            var left = previewResult.metrics.leftover_pieces || 0;
            var ordered = previewResult.metrics.ordered_pieces || 0;
            fitEl.textContent = left
                ? left + " of " + ordered + " pieces did not fit. Side and end orientations are used only after the upright load, and only when the product allows them."
                : "All " + ordered + " pieces fit in the selected containers.";
            return;
        }
        if (previewIsStale) {
            fitEl.textContent = "The load changed. Optimize again to check which pieces fit.";
            return;
        }
        if (orderedVolume == null) return;
        if (!collectLines().length || !collectContainers().length) {
            fitEl.textContent = "Add products and a container.";
        } else if (orderedVolume > capacityVolume || orderedWeight > capacityWeight) {
            fitEl.textContent = "Ordered cube or weight is over the selected containers. Some pieces may be left over.";
        } else {
            fitEl.textContent = "Ordered cube and weight are inside the container limits. Optimize checks whether each piece fits.";
        }
    }

    function markPreviewStale() {
        var stage = document.getElementById("lpStage");
        if (!previewPayload || !stage || stage.hidden) return;
        var issue = document.getElementById("issueBtn");
        var note = document.getElementById("lpStale");
        if (issue) issue.disabled = true;
        if (note) note.hidden = false;
    }

    function markActive(row) {
        document.querySelectorAll("#containerRows .lp-line").forEach(function (item) {
            item.classList.toggle("is-active", item === row);
        });
        var select = document.getElementById("libraryContainer");
        var id = row ? read(row, "container_id") : "";
        if (select && id && findById(libraryContainers, id)) select.value = String(id);
    }

    function activeContainerRow() {
        return document.querySelector("#containerRows .lp-line.is-active")
            || document.querySelector("#containerRows .lp-line");
    }

    function applyLineResults(lines) {
        var rows = document.querySelectorAll("#productRows .lp-line");
        Array.prototype.forEach.call(rows, function (row, index) {
            var line = (lines || [])[index];
            var loaded = row.querySelector("[data-loaded]");
            var left = row.querySelector("[data-left]");
            if (loaded) loaded.value = line ? String(line.loaded) : "";
            if (left) left.value = line ? String(line.leftover) : "";
        });
    }

    function applyContainerUsed(containers) {
        var rows = document.querySelectorAll("#containerRows .lp-line");
        Array.prototype.forEach.call(rows, function (row, index) {
            var used = (containers || []).filter(function (box) {
                return box.spec_index === index;
            }).length;
            var el = row.querySelector("[data-used]");
            if (el) el.value = containers ? String(used) : "";
        });
    }

    function addContainer(data) {
        var row = document.getElementById("containerTemplate").content.firstElementChild.cloneNode(true);
        document.getElementById("containerRows").appendChild(row);
        fill(row, data || { available: 1, type: "truck", load_direction: "back_to_front" });
        markActive(row);
        updateLive();
        return row;
    }

    function nextStockColor(exceptRow) {
        var used = {};
        document.querySelectorAll("#productRows .lp-line").forEach(function (row) {
            if (row === exceptRow) return;
            var value = String(read(row, "color") || "").toLowerCase();
            if (value) used[value] = true;
        });
        for (var index = 0; index < STOCK_COLORS.length; index++) {
            if (!used[STOCK_COLORS[index]]) return STOCK_COLORS[index];
        }
        var count = document.querySelectorAll("#productRows .lp-line").length - (exceptRow ? 1 : 0);
        return STOCK_COLORS[count % STOCK_COLORS.length];
    }

    function addProduct(data, assignColor) {
        var row = document.getElementById("productTemplate").content.firstElementChild.cloneNode(true);
        document.getElementById("productRows").appendChild(row);
        fill(row, data || { qty: 1, weight_lb: 0, turn_on_floor: true, stackable: true });
        if (assignColor || !read(row, "color") || String(read(row, "color")).charAt(0) !== "#") {
            write(row, "color", nextStockColor(row));
        }
        var allowed = data && data.allowed_orientations;
        if (Array.isArray(allowed) && allowed.length) {
            ORIENT_NAMES.forEach(function (name) {
                write(row, "allow_" + name, allowed.indexOf(name) !== -1);
            });
        }
        if (!read(row, "orient_mode")) write(row, "orient_mode", "all_six");
        syncProductOptions(row);
        updateLive();
        return row;
    }

    function fillSelect(select, rows, labelKey, placeholder) {
        select.innerHTML = "";
        var blank = document.createElement("option");
        blank.value = "";
        blank.textContent = placeholder;
        select.appendChild(blank);
        rows.forEach(function (row) {
            var option = document.createElement("option");
            option.value = String(row.id);
            option.textContent = row[labelKey];
            select.appendChild(option);
        });
    }

    function findById(rows, id) {
        return rows.filter(function (row) { return String(row.id) === String(id); })[0] || null;
    }

    function postJson(url, body) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        }).then(function (res) {
            return res.json().then(function (data) {
                return { ok: res.ok, data: data || {} };
            });
        });
    }

    function loadLibraries() {
        return Promise.all([
            fetch("/load-planning/api/containers").then(function (res) { return res.json(); }),
            fetch("/load-planning/api/products").then(function (res) { return res.json(); })
        ]).then(function (parts) {
            libraryContainers = (parts[0] && parts[0].containers) || [];
            libraryProducts = (parts[1] && parts[1].products) || [];
            var selectedContainer = document.getElementById("libraryContainer").value;
            fillSelect(document.getElementById("libraryContainer"), libraryContainers, "label", "Choose a container");
            fillSelect(document.getElementById("libraryProduct"), libraryProducts, "name", "Choose a product");
            if (selectedContainer) document.getElementById("libraryContainer").value = selectedContainer;
            if (!document.querySelector("#containerRows .lp-line")) {
                var van = libraryContainers.filter(function (row) { return row.label === "53 ft dry van"; })[0];
                addContainer(van ? {
                    container_id: van.id,
                    label: van.label,
                    type: van.type,
                    length_in: van.length_in,
                    width_in: van.width_in,
                    height_in: van.height_in,
                    max_payload_lb: van.max_payload_lb,
                    load_direction: van.load_direction,
                    available: 1
                } : { available: 1, type: "truck", load_direction: "back_to_front" });
                if (van) document.getElementById("libraryContainer").value = String(van.id);
            }
            if (!document.querySelector("#productRows .lp-line")) addProduct();
        }).catch(function () {
            if (!document.querySelector("#containerRows .lp-line")) addContainer();
            if (!document.querySelector("#productRows .lp-line")) addProduct();
        });
    }

    function libraryContainerPayload(chosen, available) {
        return {
            container_id: chosen.id,
            label: chosen.label,
            type: chosen.type,
            length_in: chosen.length_in,
            width_in: chosen.width_in,
            height_in: chosen.height_in,
            max_payload_lb: chosen.max_payload_lb,
            load_direction: chosen.load_direction,
            available: available || 1
        };
    }

    function applyInput(data) {
        previewPayload = null;
        previewResult = null;
        var stage = document.getElementById("lpStage");
        if (stage) stage.hidden = true;
        document.getElementById("containerRows").innerHTML = "";
        document.getElementById("productRows").innerHTML = "";
        (data.containers || []).forEach(addContainer);
        (data.lines || []).forEach(addProduct);
        if (!document.querySelector("#containerRows .lp-line")) addContainer();
        if (!document.querySelector("#productRows .lp-line")) addProduct();
        var notes = document.getElementById("plan_notes");
        if (notes) notes.value = data.notes || "";
        var include = document.getElementById("include_customer");
        if (include) {
            include.checked = !!data.include_customer;
            include.dispatchEvent(new Event("change"));
        }
        var name = document.getElementById("customer_name");
        var email = document.getElementById("contact_email");
        if (name) name.value = data.customer_name || "";
        if (email) email.value = data.contact_email || "";
        updateLive();
    }

    document.getElementById("libraryContainer").addEventListener("change", function () {
        var chosen = findById(libraryContainers, document.getElementById("libraryContainer").value);
        if (!chosen) return;
        var row = activeContainerRow();
        if (!row) row = addContainer();
        var available = read(row, "available") || 1;
        fill(row, libraryContainerPayload(chosen, available));
        markActive(row);
        showMessage("", false);
        updateLive();
    });

    document.getElementById("addAnotherContainer").addEventListener("click", function () {
        var row = addContainer({ available: 1, type: "truck", load_direction: "back_to_front", label: "" });
        document.getElementById("libraryContainer").value = "";
        markActive(row);
        showMessage("Choose a container. Its details fill this row.", true);
    });

    document.getElementById("addCustomContainer").addEventListener("click", function () {
        var row = addContainer({ available: 1, type: "truck", load_direction: "back_to_front" });
        document.getElementById("libraryContainer").value = "";
        markActive(row);
    });

    document.getElementById("addLibraryProduct").addEventListener("click", function () {
        var chosen = findById(libraryProducts, document.getElementById("libraryProduct").value);
        if (!chosen) {
            showMessage("Choose a saved product first.", false);
            return;
        }
        showMessage("", false);
        addProduct({
            product_id: chosen.id,
            name: chosen.name,
            length_in: chosen.length_in,
            width_in: chosen.width_in,
            height_in: chosen.height_in,
            weight_lb: chosen.weight_lb,
            qty: 1,
            turn_on_floor: chosen.turn_on_floor,
            stackable: chosen.stackable,
            on_floor_only: chosen.on_floor_only,
            on_top_only: chosen.on_top_only,
            max_stack: chosen.max_stack,
            supported_weight_lb: chosen.supported_weight_lb,
            stack_index: chosen.stack_index,
            notes: chosen.notes || "",
            shape: chosen.shape || "box",
            orient_mode: chosen.orient_mode || "all_six",
            allowed_orientations: chosen.allowed_orientations || [],
            back_depth: chosen.back_depth,
            seat_height: chosen.seat_height,
            stem_width: chosen.stem_width,
            bar_depth: chosen.bar_depth
        }, true);
    });

    document.getElementById("addBlankProduct").addEventListener("click", function () {
        addProduct(null, true);
    });

    document.getElementById("containerRows").addEventListener("click", function (event) {
        var row = event.target.closest(".lp-line");
        if (row) markActive(row);
        var button = event.target.closest("[data-action]");
        if (!button) return;
        row = button.closest(".lp-line");
        if (button.getAttribute("data-action") === "remove") {
            row.remove();
            updateLive();
            return;
        }
        var body = collectContainers().filter(function (_item, index) {
            return document.querySelectorAll("#containerRows .lp-line")[index] === row;
        })[0];
        postJson("/load-planning/api/containers", body).then(function (result) {
            if (!result.ok) {
                showMessage(result.data.error || "Could not save that container.", false);
                return;
            }
            showMessage("Container saved.", true);
            return loadLibraries();
        }).catch(function () {
            showMessage("Could not save that container.", false);
        });
    });

    document.getElementById("productRows").addEventListener("click", function (event) {
        var tab = event.target.closest("[data-tab]");
        if (tab) {
            var card = tab.closest(".lp-product");
            var name = tab.getAttribute("data-tab");
            card.querySelectorAll("[data-tab]").forEach(function (button) {
                button.classList.toggle("is-on", button === tab);
            });
            card.querySelectorAll("[data-panel]").forEach(function (panel) {
                panel.hidden = panel.getAttribute("data-panel") !== name;
            });
            return;
        }
        var button = event.target.closest("[data-action]");
        if (!button) return;
        var row = button.closest(".lp-line");
        if (button.getAttribute("data-action") === "remove") {
            row.remove();
            updateLive();
            return;
        }
        var rows = document.querySelectorAll("#productRows .lp-line");
        var body = null;
        Array.prototype.forEach.call(rows, function (candidate, index) {
            if (candidate === row) body = collectLines()[index];
        });
        postJson("/load-planning/api/products", body).then(function (result) {
            if (!result.ok) {
                showMessage(result.data.error || "Could not save that product.", false);
                return;
            }
            if (result.data.product) write(row, "product_id", result.data.product.id);
            showMessage("Product saved.", true);
            return loadLibraries();
        }).catch(function () {
            showMessage("Could not save that product.", false);
        });
    });

    document.getElementById("containerRows").addEventListener("change", function (event) {
        if (event.target.getAttribute("data-field") === "type") {
            var row = event.target.closest(".lp-line");
            var kind = event.target.value;
            write(row, "load_direction", (kind === "pallet" || kind === "box") ? "bottom_to_top" : "back_to_front");
        }
        updateLive();
    });

    document.getElementById("quoteForm").addEventListener("input", updateLive);
    document.getElementById("quoteForm").addEventListener("change", function (event) {
        var row = event.target.closest && event.target.closest("#productRows .lp-line");
        if (row && event.target.getAttribute("data-field") === "orient_mode") {
            Array.prototype.forEach.call(fields(row, "orient_mode"), function (el) {
                el.checked = el === event.target;
            });
        }
        if (row && (event.target.getAttribute("data-field") === "shape" || event.target.getAttribute("data-field") === "orient_mode")) {
            syncProductOptions(row);
        }
        updateLive();
    });

    function describePreview(result) {
        var metrics = result.metrics || {};
        var text = (metrics.loaded_pieces || 0) + " of " + (metrics.ordered_pieces || 0)
            + " pieces loaded. Cube " + metrics.cube_util_pct + "%. Weight " + metrics.weight_util_pct + "%.";
        if (result.warnings && result.warnings.length) text += " " + result.warnings.join(" ");
        return text;
    }

    document.getElementById("quoteForm").addEventListener("submit", function (event) {
        event.preventDefault();
        var button = document.getElementById("optimizeBtn");
        var body = payload();
        showMessage("", false);
        button.disabled = true;
        var previous = button.textContent;
        button.textContent = "Optimizing...";
        postJson("/load-planning/preview", body).then(function (result) {
            button.disabled = false;
            button.textContent = previous;
            if (!result.ok || !result.data.result) {
                showMessage(result.data.error || "The load could not be planned.", false);
                return;
            }
            previewPayload = body;
            previewResult = result.data.result;
            applyLineResults(result.data.result.lines);
            applyContainerUsed(result.data.result.containers);
            var stage = document.getElementById("lpStage");
            var summary = document.getElementById("lpStageSummary");
            var note = document.getElementById("lpStale");
            var issue = document.getElementById("issueBtn");
            if (summary) summary.textContent = describePreview(result.data.result);
            if (note) note.hidden = true;
            if (issue) issue.disabled = false;
            if (stage) {
                stage.hidden = false;
                stage.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
            if (window.LpView) window.LpView.show(result.data.result);
            refreshFit();
        }).catch(function () {
            showMessage("The load could not be planned. Try again.", false);
            button.disabled = false;
            button.textContent = previous;
        });
    });

    document.getElementById("issueBtn").addEventListener("click", function () {
        var button = document.getElementById("issueBtn");
        if (!previewPayload || button.disabled) return;
        showMessage("", false);
        button.disabled = true;
        var previous = button.textContent;
        button.textContent = "Issuing...";
        postJson("/load-planning/optimize", previewPayload).then(function (result) {
            if (!result.ok || !result.data.url) {
                showMessage(result.data.error || "The plan could not be issued.", false);
                button.disabled = false;
                button.textContent = previous;
                return;
            }
            window.location = result.data.url;
        }).catch(function () {
            showMessage("The plan could not be issued. Try again.", false);
            button.disabled = false;
            button.textContent = previous;
        });
    });

    var prevBtn = document.getElementById("load_previous_quote_btn");
    var prevList = document.getElementById("load_previous_quote_list");
    var prevWrap = document.querySelector(".header-quote-wrap");
    if (prevBtn && prevList) {
        function closePrev() {
            prevList.hidden = true;
            prevBtn.setAttribute("aria-expanded", "false");
        }
        prevBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            var open = prevList.hidden;
            prevList.hidden = !open;
            prevBtn.setAttribute("aria-expanded", open ? "true" : "false");
        });
        prevList.querySelectorAll("[data-quote]").forEach(function (item) {
            item.addEventListener("click", function () {
                var number = item.getAttribute("data-quote");
                fetch("/load-planning/plan/" + encodeURIComponent(number) + "/input")
                    .then(function (res) { return res.json(); })
                    .then(function (data) {
                        applyInput(data || {});
                        prevBtn.textContent = item.textContent || "Select a plan";
                        closePrev();
                        showMessage("Loaded " + (item.textContent || "plan") + ".", true);
                    })
                    .catch(function () {
                        showMessage("That plan could not be loaded.", false);
                        closePrev();
                    });
            });
        });
        document.addEventListener("click", function (event) {
            if (prevWrap && !prevWrap.contains(event.target)) closePrev();
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") closePrev();
        });
    }

    loadLibraries();
})();
