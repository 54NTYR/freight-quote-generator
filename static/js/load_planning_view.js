/* 3D load preview. Origin is the nose, left wall, and floor.
   x runs toward the door, y toward the right wall, z up. */
(function () {
    var VIEWS = {
        top: { yaw: -Math.PI / 2, pitch: 1.28 },
        left: { yaw: -Math.PI / 2, pitch: 0.18 },
        right: { yaw: Math.PI / 2, pitch: 0.18 },
        front: { yaw: 0, pitch: 0.16 },
        back: { yaw: Math.PI, pitch: 0.16 },
        fl: { yaw: -0.72, pitch: 0.52 },
        fr: { yaw: 0.72, pitch: 0.52 },
        bl: { yaw: -2.42, pitch: 0.52 },
        br: { yaw: 2.42, pitch: 0.52 }
    };

    var state = {
        result: null,
        index: 0,
        step: 0,
        view: "fl",
        yaw: VIEWS.fl.yaw,
        pitch: VIEWS.fl.pitch,
        zoom: 1,
        panX: 0,
        panY: 0,
        ids: false,
        style: "solid",
        quad: false
    };
    var canvas = null;
    var playTimer = null;
    var bound = false;
    var dragging = false;
    var panning = false;
    var lastX = 0;
    var lastY = 0;

    function sub(a, b) {
        return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
    }

    function dot(a, b) {
        return a.x * b.x + a.y * b.y + a.z * b.z;
    }

    function cross(a, b) {
        return {
            x: a.y * b.z - a.z * b.y,
            y: a.z * b.x - a.x * b.z,
            z: a.x * b.y - a.y * b.x
        };
    }

    function norm(v) {
        var len = Math.sqrt(dot(v, v)) || 1;
        return { x: v.x / len, y: v.y / len, z: v.z / len };
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function currentBox() {
        var boxes = (state.result && state.result.containers) || [];
        return boxes[state.index] || null;
    }

    function ordered(box) {
        return (box.placements || []).slice().sort(function (a, b) {
            return (a.sequence || 0) - (b.sequence || 0);
        });
    }

    function maxStep() {
        var box = currentBox();
        return box ? ordered(box).length : 0;
    }

    function visible(box) {
        return ordered(box).slice(0, state.step);
    }

    function fmt(value) {
        var rounded = Math.round(Number(value) * 10) / 10;
        return String(rounded);
    }

    function hexToRgb(hex) {
        var raw = String(hex || "#1e3c72").replace("#", "");
        if (raw.length === 3) {
            raw = raw.split("").map(function (ch) { return ch + ch; }).join("");
        }
        var value = parseInt(raw, 16);
        if (!isFinite(value)) value = 0x1e3c72;
        return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
    }

    function shadeRgb(hex, normal) {
        var rgb = hexToRgb(hex);
        var light = norm({ x: 0.4, y: -0.35, z: 0.84 });
        var amount = 0.42 + 0.58 * Math.abs(dot(norm(normal), light));
        return [
            Math.round(rgb.r * amount),
            Math.round(rgb.g * amount),
            Math.round(rgb.b * amount)
        ];
    }

    var paintScratch = null;

    function scratchCanvas(w, h) {
        if (!paintScratch) paintScratch = document.createElement("canvas");
        if (paintScratch.width !== w || paintScratch.height !== h) {
            paintScratch.width = w;
            paintScratch.height = h;
        }
        return paintScratch;
    }

    function fillTriangle(data, depth, width, height, a, b, c, rgb, alpha) {
        if (a.y > b.y) { var swap = a; a = b; b = swap; }
        if (b.y > c.y) { var swap2 = b; b = c; c = swap2; }
        if (a.y > b.y) { var swap3 = a; a = b; b = swap3; }
        var yStart = Math.max(0, Math.ceil(a.y));
        var yEnd = Math.min(height - 1, Math.floor(c.y));
        if (yEnd < yStart) return;

        function edge(y, p, q) {
            var dy = q.y - p.y;
            if (Math.abs(dy) < 1e-4) return null;
            var u = (y - p.y) / dy;
            if (u < 0 || u > 1) return null;
            return { x: p.x + (q.x - p.x) * u, inv: p.inv + (q.inv - p.inv) * u };
        }

        for (var y = yStart; y <= yEnd; y++) {
            var sampleY = y + 0.5;
            var longEdge = edge(sampleY, a, c);
            var shortEdge = sampleY < b.y ? edge(sampleY, a, b) : edge(sampleY, b, c);
            if (!longEdge || !shortEdge) continue;
            var left = longEdge;
            var right = shortEdge;
            if (left.x > right.x) {
                var tmp = left;
                left = right;
                right = tmp;
            }
            var xStart = Math.max(0, Math.ceil(left.x));
            var xEnd = Math.min(width - 1, Math.floor(right.x));
            if (xEnd - xStart > width) continue;
            var spanX = right.x - left.x;
            for (var x = xStart; x <= xEnd; x++) {
                var u = spanX < 1e-6 ? 0 : (x + 0.5 - left.x) / spanX;
                var inv = left.inv + (right.inv - left.inv) * u;
                if (!(inv > 0)) continue;
                var index = y * width + x;
                if (inv <= depth[index]) continue;
                depth[index] = inv;
                var offset = index * 4;
                var src = alpha / 255;
                data[offset] = Math.round(rgb[0] * src + 251 * (1 - src));
                data[offset + 1] = Math.round(rgb[1] * src + 250 * (1 - src));
                data[offset + 2] = Math.round(rgb[2] * src + 247 * (1 - src));
                data[offset + 3] = 255;
            }
        }
    }

    function invOf(point) {
        return point.z > 0.1 ? 1 / point.z : 0;
    }

    function plotEdge(data, depth, width, height, a, b) {
        if (!isFinite(a.x) || !isFinite(b.x) || !isFinite(a.y) || !isFinite(b.y)) return;
        var reach = Math.hypot(b.x - a.x, b.y - a.y);
        if (reach > (width + height) * 3) return;
        var aInv = a.inv || invOf(a);
        var bInv = b.inv || invOf(b);
        var steps = Math.max(1, Math.ceil(reach));
        for (var step = 0; step <= steps; step++) {
            var u = step / steps;
            var x = Math.round(a.x + (b.x - a.x) * u);
            var y = Math.round(a.y + (b.y - a.y) * u);
            if (x < 0 || y < 0 || x >= width || y >= height) continue;
            var inv = aInv + (bInv - aInv) * u;
            var index = y * width + x;
            if (inv < depth[index] * 0.997) continue;
            var offset = index * 4;
            data[offset] = Math.round(data[offset] * 0.62);
            data[offset + 1] = Math.round(data[offset + 1] * 0.62);
            data[offset + 2] = Math.round(data[offset + 2] * 0.62);
        }
    }

    function camera(box, yaw, pitch) {
        var center = { x: box.length_in / 2, y: box.width_in / 2, z: box.height_in / 2 };
        var dist = 2.4 * Math.max(box.length_in, box.width_in, box.height_in, 1);
        var eye = {
            x: center.x + dist * Math.cos(pitch) * Math.cos(yaw),
            y: center.y + dist * Math.cos(pitch) * Math.sin(yaw),
            z: center.z + dist * Math.sin(pitch)
        };
        var forward = norm(sub(center, eye));
        var worldUp = Math.abs(forward.z) > 0.96 ? { x: 0, y: 1, z: 0 } : { x: 0, y: 0, z: 1 };
        var right = norm(cross(forward, worldUp));
        var up = cross(right, forward);
        return { eye: eye, forward: forward, right: right, up: up, center: center, dist: dist };
    }

    function project(point, cam, cx, cy, span) {
        var delta = sub(point, cam.eye);
        var x = dot(delta, cam.right);
        var y = dot(delta, cam.up);
        var z = dot(delta, cam.forward);
        var scale = span / Math.max(0.15, z);
        return { x: cx + x * scale, y: cy - y * scale, z: z };
    }

    function face(points, normal, color, item) {
        return { points: points, normal: normal, color: color, item: item || null };
    }

    function boxFaces(origin, size, color, item) {
        var x0 = origin.x;
        var y0 = origin.y;
        var z0 = origin.z;
        var x1 = origin.x + size.x;
        var y1 = origin.y + size.y;
        var z1 = origin.z + size.z;
        var p = [
            { x: x0, y: y0, z: z0 },
            { x: x1, y: y0, z: z0 },
            { x: x1, y: y1, z: z0 },
            { x: x0, y: y1, z: z0 },
            { x: x0, y: y0, z: z1 },
            { x: x1, y: y0, z: z1 },
            { x: x1, y: y1, z: z1 },
            { x: x0, y: y1, z: z1 }
        ];
        return [
            face([p[4], p[5], p[6], p[7]], { x: 0, y: 0, z: 1 }, color, item),
            face([p[0], p[3], p[2], p[1]], { x: 0, y: 0, z: -1 }, color, item),
            face([p[1], p[2], p[6], p[5]], { x: 1, y: 0, z: 0 }, color, item),
            face([p[0], p[4], p[7], p[3]], { x: -1, y: 0, z: 0 }, color, item),
            face([p[3], p[7], p[6], p[2]], { x: 0, y: 1, z: 0 }, color, item),
            face([p[0], p[1], p[5], p[4]], { x: 0, y: -1, z: 0 }, color, item)
        ];
    }

    function cylinderProfile(origin, size, item) {
        var axis = (item && item.cylinder_axis) || "x";
        if (axis === "x") {
            return {
                axis: "x",
                u: "y",
                v: "z",
                along: "x",
                cu: origin.y + size.y / 2,
                cv: origin.z + size.z / 2,
                start: origin.x,
                end: origin.x + size.x,
                radius: Math.min(size.y, size.z) / 2
            };
        }
        if (axis === "y") {
            return {
                axis: "y",
                u: "x",
                v: "z",
                along: "y",
                cu: origin.x + size.x / 2,
                cv: origin.z + size.z / 2,
                start: origin.y,
                end: origin.y + size.y,
                radius: Math.min(size.x, size.z) / 2
            };
        }
        return {
            axis: "z",
            u: "x",
            v: "y",
            along: "z",
            cu: origin.x + size.x / 2,
            cv: origin.y + size.y / 2,
            start: origin.z,
            end: origin.z + size.z,
            radius: Math.min(size.x, size.y) / 2
        };
    }

    function cylinderRing(profile, along) {
        var points = [];
        for (var index = 0; index < 24; index++) {
            var angle = (index / 24) * Math.PI * 2;
            var point = { x: 0, y: 0, z: 0 };
            point[profile.u] = profile.cu + Math.cos(angle) * profile.radius;
            point[profile.v] = profile.cv + Math.sin(angle) * profile.radius;
            point[profile.along] = along;
            points.push(point);
        }
        return points;
    }

    function cylinderFaces(origin, size, color, item) {
        var profile = cylinderProfile(origin, size, item);
        var faces = [];
        var bottom = [];
        var top = [];
        for (var index = 0; index < 24; index++) {
            var a0 = (index / 24) * Math.PI * 2;
            var a1 = ((index + 1) / 24) * Math.PI * 2;
            var p0 = { x: 0, y: 0, z: 0 };
            var p1 = { x: 0, y: 0, z: 0 };
            var q0 = { x: 0, y: 0, z: 0 };
            var q1 = { x: 0, y: 0, z: 0 };
            p0[profile.u] = profile.cu + Math.cos(a0) * profile.radius;
            p0[profile.v] = profile.cv + Math.sin(a0) * profile.radius;
            p0[profile.along] = profile.start;
            p1[profile.u] = profile.cu + Math.cos(a1) * profile.radius;
            p1[profile.v] = profile.cv + Math.sin(a1) * profile.radius;
            p1[profile.along] = profile.start;
            q1[profile.u] = p1[profile.u];
            q1[profile.v] = p1[profile.v];
            q1[profile.along] = profile.end;
            q0[profile.u] = p0[profile.u];
            q0[profile.v] = p0[profile.v];
            q0[profile.along] = profile.end;
            var mid = (a0 + a1) / 2;
            var normal = { x: 0, y: 0, z: 0 };
            normal[profile.u] = Math.cos(mid);
            normal[profile.v] = Math.sin(mid);
            faces.push(face([p0, p1, q1, q0], normal, color, item));
            bottom.push(p0);
            top.push(q0);
        }
        var endNormal = { x: 0, y: 0, z: 0 };
        var startNormal = { x: 0, y: 0, z: 0 };
        endNormal[profile.along] = 1;
        startNormal[profile.along] = -1;
        faces.push(face(top, endNormal, color, item));
        faces.push(face(bottom.slice().reverse(), startNormal, color, item));
        return faces;
    }

    function shapeFaces(part, shape, color, item) {
        var origin = { x: part.x, y: part.y, z: part.z };
        var size = { x: part.length_in, y: part.width_in, z: part.height_in };
        if (shape === "cylinder") return cylinderFaces(origin, size, color, item);
        return boxFaces(origin, size, color, item);
    }

    function edgesOf(origin, size) {
        var x0 = origin.x;
        var y0 = origin.y;
        var z0 = origin.z;
        var x1 = origin.x + size.x;
        var y1 = origin.y + size.y;
        var z1 = origin.z + size.z;
        var p = [
            { x: x0, y: y0, z: z0 },
            { x: x1, y: y0, z: z0 },
            { x: x1, y: y1, z: z0 },
            { x: x0, y: y1, z: z0 },
            { x: x0, y: y0, z: z1 },
            { x: x1, y: y0, z: z1 },
            { x: x1, y: y1, z: z1 },
            { x: x0, y: y1, z: z1 }
        ];
        return [
            [p[0], p[1]], [p[1], p[2]], [p[2], p[3]], [p[3], p[0]],
            [p[4], p[5]], [p[5], p[6]], [p[6], p[7]], [p[7], p[4]],
            [p[0], p[4]], [p[1], p[5]], [p[2], p[6]], [p[3], p[7]]
        ];
    }

    function drawScene(ctx, box, pieces, yaw, pitch, left, top, width, height) {
        var cam = camera(box, yaw, pitch);
        var cx = left + width / 2 + (state.quad ? 0 : state.panX);
        var cy = top + height / 2 + (state.quad ? 0 : state.panY);
        var corners = [
            { x: 0, y: 0, z: 0 },
            { x: box.length_in, y: 0, z: 0 },
            { x: box.length_in, y: box.width_in, z: 0 },
            { x: 0, y: box.width_in, z: 0 },
            { x: 0, y: 0, z: box.height_in },
            { x: box.length_in, y: 0, z: box.height_in },
            { x: box.length_in, y: box.width_in, z: box.height_in },
            { x: 0, y: box.width_in, z: box.height_in }
        ];
        var minX = Infinity;
        var maxX = -Infinity;
        var minY = Infinity;
        var maxY = -Infinity;
        corners.forEach(function (point) {
            var projected = project(point, cam, 0, 0, 1000);
            if (projected.z <= 0.1) return;
            if (projected.x < minX) minX = projected.x;
            if (projected.x > maxX) maxX = projected.x;
            if (projected.y < minY) minY = projected.y;
            if (projected.y > maxY) maxY = projected.y;
        });
        var fitted = 1000 * Math.min(
            (width * 0.86) / Math.max(maxX - minX, 1),
            (height * 0.78) / Math.max(maxY - minY, 1)
        );
        var span = fitted / state.zoom;

        function visibleFace(item) {
            var center = { x: 0, y: 0, z: 0 };
            item.points.forEach(function (point) {
                center.x += point.x;
                center.y += point.y;
                center.z += point.z;
            });
            center.x /= item.points.length;
            center.y /= item.points.length;
            center.z /= item.points.length;
            if (dot(item.normal, sub(cam.eye, center)) <= 0.001) return null;
            var projected = item.points.map(function (point) {
                return project(point, cam, cx, cy, span);
            });
            if (projected.every(function (point) { return point.z <= 0.1; })) return null;
            var depth = 0;
            projected.forEach(function (point) { depth += point.z; });
            return {
                face: item,
                projected: projected,
                depth: depth / projected.length,
                center: project(center, cam, cx, cy, span)
            };
        }

        var drawnFaces = [];
        function keepFace(item) {
            var visible = visibleFace(item);
            if (visible) drawnFaces.push(visible);
        }
        keepFace(face([
            { x: 0, y: 0, z: 0 },
            { x: box.length_in, y: 0, z: 0 },
            { x: box.length_in, y: box.width_in, z: 0 },
            { x: 0, y: box.width_in, z: 0 }
        ], { x: 0, y: 0, z: 1 }, "#f4f1ea", null));
        pieces.forEach(function (item) {
            var parts = item.parts && item.parts.length ? item.parts : [item];
            var crown = 0;
            parts.forEach(function (part) {
                crown = Math.max(crown, part.z + part.height_in);
            });
            var labeled = false;
            parts.forEach(function (part) {
                var showLabel = !labeled && Math.abs(part.z + part.height_in - crown) < 0.05;
                if (showLabel) labeled = true;
                shapeFaces(
                    part,
                    item.shape,
                    item.color || "#e6194b",
                    showLabel ? item : { color: item.color, plan_text: "", sequence: "", shape: item.shape }
                ).forEach(keepFace);
            });
        });

        if (state.style === "ghost") {
            drawnFaces.slice().sort(function (a, b) { return b.depth - a.depth; }).forEach(function (item) {
                var rgb = item.face.item ? shadeRgb(item.face.color, item.face.normal) : [244, 241, 234];
                ctx.beginPath();
                item.projected.forEach(function (point, index) {
                    if (index === 0) ctx.moveTo(point.x, point.y);
                    else ctx.lineTo(point.x, point.y);
                });
                ctx.closePath();
                ctx.globalAlpha = item.face.item ? 0.4 : 0.7;
                ctx.fillStyle = "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")";
                ctx.fill();
                ctx.globalAlpha = 0.9;
                ctx.lineWidth = 1.25;
                ctx.strokeStyle = item.face.item
                    ? "rgb(" + Math.round(rgb[0] * 0.45) + "," + Math.round(rgb[1] * 0.45) + "," + Math.round(rgb[2] * 0.45) + ")"
                    : "#b7b1a6";
                ctx.stroke();
                ctx.globalAlpha = 1;
            });
            if (state.ids) {
                drawnFaces.forEach(function (item) {
                    if (!item.face.item || item.face.normal.z <= 0.5) return;
                    var spanX = 0;
                    item.projected.forEach(function (point) {
                        spanX = Math.max(spanX, Math.abs(point.x - item.center.x));
                    });
                    if (spanX * 2 <= 18) return;
                    ctx.fillStyle = "#1d1d1f";
                    ctx.font = "600 12px Segoe UI, sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText(item.face.item.plan_text || String(item.face.item.sequence), item.center.x, item.center.y);
                });
            }
        } else if (state.style !== "wire") {
            var bufferW = Math.max(1, Math.round(width));
            var bufferH = Math.max(1, Math.round(height));
            var scratch = scratchCanvas(bufferW, bufferH);
            var pixels = scratch.getContext("2d").createImageData(bufferW, bufferH);
            var data = pixels.data;
            var depth = new Float32Array(bufferW * bufferH);
            for (var bg = 0; bg < data.length; bg += 4) {
                data[bg] = 251;
                data[bg + 1] = 250;
                data[bg + 2] = 247;
                data[bg + 3] = 255;
            }
            var alpha = 255;
            function localPoint(point) {
                return { x: point.x - left, y: point.y - top, z: point.z, inv: invOf(point) };
            }
            function fillPolygon(local, rgb) {
                for (var index = 1; index < local.length - 1; index++) {
                    fillTriangle(data, depth, bufferW, bufferH, local[0], local[index], local[index + 1], rgb, alpha);
                }
            }
            drawnFaces.forEach(function (item) {
                var rgb = item.face.item ? shadeRgb(item.face.color, item.face.normal) : [247, 244, 238];
                fillPolygon(item.projected.map(localPoint), rgb);
            });
            var labels = [];
            drawnFaces.forEach(function (item) {
                if (!item.face.item) return;
                if (state.style !== "ghost") {
                    var ring = item.projected.map(localPoint);
                    for (var edgeIndex = 0; edgeIndex < ring.length; edgeIndex++) {
                        plotEdge(data, depth, bufferW, bufferH, ring[edgeIndex], ring[(edgeIndex + 1) % ring.length]);
                    }
                }
                if (state.ids && item.face.normal.z > 0.5) {
                    var lx = Math.round(item.center.x - left);
                    var ly = Math.round(item.center.y - top);
                    if (lx >= 0 && ly >= 0 && lx < bufferW && ly < bufferH) {
                        var stored = depth[ly * bufferW + lx];
                        if (invOf(item.center) >= stored * 0.997) labels.push(item);
                    }
                }
            });
            scratch.getContext("2d").putImageData(pixels, 0, 0);
            ctx.drawImage(scratch, left, top, width, height);
            labels.forEach(function (item) {
                var spanX = 0;
                item.projected.forEach(function (point) {
                    spanX = Math.max(spanX, Math.abs(point.x - item.center.x));
                });
                spanX *= 2;
                if (spanX <= 18) return;
                ctx.fillStyle = "#1d1d1f";
                ctx.font = "600 12px Segoe UI, sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(item.face.item.plan_text || String(item.face.item.sequence), item.center.x, item.center.y);
            });
        }
        function strokeEdges(origin, size, color, widthPx) {
            ctx.strokeStyle = color;
            ctx.lineWidth = widthPx;
            edgesOf(origin, size).forEach(function (pair) {
                var a = project(pair[0], cam, cx, cy, span);
                var b = project(pair[1], cam, cx, cy, span);
                if (a.z <= 0.1 || b.z <= 0.1) return;
                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.stroke();
            });
        }
        function strokeLoop(points, color) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            var moved = false;
            points.forEach(function (point) {
                var projected = project(point, cam, cx, cy, span);
                if (projected.z <= 0.1) return;
                if (!moved) {
                    ctx.moveTo(projected.x, projected.y);
                    moved = true;
                } else {
                    ctx.lineTo(projected.x, projected.y);
                }
            });
            if (moved) {
                ctx.closePath();
                ctx.stroke();
            }
        }
        if (state.style === "wire") {
            pieces.forEach(function (item) {
                var parts = item.parts && item.parts.length ? item.parts : [item];
                parts.forEach(function (part) {
                    if (item.shape === "cylinder") {
                        var profile = cylinderProfile(
                            { x: part.x, y: part.y, z: part.z },
                            { x: part.length_in, y: part.width_in, z: part.height_in },
                            item
                        );
                        strokeLoop(cylinderRing(profile, profile.start), item.color || "#e6194b");
                        strokeLoop(cylinderRing(profile, profile.end), item.color || "#e6194b");
                        return;
                    }
                    strokeEdges(
                        { x: part.x, y: part.y, z: part.z },
                        { x: part.length_in, y: part.width_in, z: part.height_in },
                        item.color || "#e6194b",
                        1.4
                    );
                });
            });
            if (state.ids) {
                drawnFaces.forEach(function (item) {
                    if (!item.face.item || item.face.normal.z <= 0.5) return;
                    ctx.fillStyle = "#1d1d1f";
                    ctx.font = "600 12px Segoe UI, sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText(item.face.item.plan_text || String(item.face.item.sequence), item.center.x, item.center.y);
                });
            }
        }
        strokeEdges(
            { x: 0, y: 0, z: 0 },
            { x: box.length_in, y: box.width_in, z: box.height_in },
            "#1e3c72",
            1.6
        );
        ctx.strokeStyle = "#c4a000";
        ctx.lineWidth = 2;
        var door = [
            [{ x: box.length_in, y: 0, z: 0 }, { x: box.length_in, y: box.width_in, z: 0 }],
            [{ x: box.length_in, y: box.width_in, z: 0 }, { x: box.length_in, y: box.width_in, z: box.height_in }],
            [{ x: box.length_in, y: box.width_in, z: box.height_in }, { x: box.length_in, y: 0, z: box.height_in }],
            [{ x: box.length_in, y: 0, z: box.height_in }, { x: box.length_in, y: 0, z: 0 }]
        ];
        door.forEach(function (pair) {
            var a = project(pair[0], cam, cx, cy, span);
            var b = project(pair[1], cam, cx, cy, span);
            if (a.z <= 0.1 || b.z <= 0.1) return;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
        });
        if (!state.quad) {
            label(ctx, cam, cx, cy, span, { x: 0, y: -8, z: 0 }, { x: box.length_in, y: -8, z: 0 }, fmt(box.length_in) + " in");
            label(ctx, cam, cx, cy, span, { x: box.length_in + 8, y: 0, z: 0 }, { x: box.length_in + 8, y: box.width_in, z: 0 }, fmt(box.width_in) + " in");
            label(ctx, cam, cx, cy, span, { x: box.length_in + 8, y: box.width_in, z: 0 }, { x: box.length_in + 8, y: box.width_in, z: box.height_in }, fmt(box.height_in) + " in");
        }
    }

    function label(ctx, cam, cx, cy, span, a, b, text) {
        var pa = project(a, cam, cx, cy, span);
        var pb = project(b, cam, cx, cy, span);
        if (pa.z <= 0.1 || pb.z <= 0.1) return;
        ctx.fillStyle = "#1e3c72";
        ctx.font = "600 12px Segoe UI, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, (pa.x + pb.x) / 2, (pa.y + pb.y) / 2);
    }

    function resize() {
        if (!canvas) return;
        var wrap = canvas.parentElement;
        var width = Math.max(320, wrap.clientWidth);
        var height = Math.max(380, Math.min(560, Math.round(width * 0.62)));
        var ratio = window.devicePixelRatio || 1;
        var nextW = Math.round(width * ratio);
        var nextH = Math.round(height * ratio);
        if (canvas.width !== nextW || canvas.height !== nextH) {
            canvas.width = nextW;
            canvas.height = nextH;
        }
        if (canvas.style.height !== height + "px") canvas.style.height = height + "px";
        draw();
    }

    function draw() {
        if (!canvas) return;
        var ctx = canvas.getContext("2d");
        var ratio = window.devicePixelRatio || 1;
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        var width = canvas.width / ratio;
        var height = canvas.height / ratio;
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = "#fbfaf7";
        ctx.fillRect(0, 0, width, height);
        var box = currentBox();
        if (!box) {
            ctx.fillStyle = "#1e3c72";
            ctx.font = "600 16px Segoe UI, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("Nothing loaded yet.", width / 2, height / 2);
            return;
        }
        var pieces = visible(box);
        if (state.quad) {
            var views = ["fl", "fr", "bl", "br"];
            var halfW = width / 2;
            var halfH = height / 2;
            views.forEach(function (name, index) {
                var view = VIEWS[name];
                var col = index % 2;
                var row = Math.floor(index / 2);
                ctx.save();
                ctx.beginPath();
                ctx.rect(col * halfW, row * halfH, halfW, halfH);
                ctx.clip();
                drawScene(ctx, box, pieces, view.yaw, view.pitch, col * halfW, row * halfH, halfW, halfH);
                ctx.restore();
                ctx.strokeStyle = "#e4e0d8";
                ctx.strokeRect(col * halfW + 0.5, row * halfH + 0.5, halfW - 1, halfH - 1);
            });
        } else {
            drawScene(ctx, box, pieces, state.yaw, state.pitch, 0, 0, width, height);
        }
    }

    function alongUsed(box, pieces) {
        var upward = box.load_direction === "bottom_to_top";
        var used = 0;
        pieces.forEach(function (item) {
            var end = upward ? item.z + item.height_in : item.x + item.length_in;
            if (end > used) used = end;
        });
        var cap = upward ? box.height_in : box.length_in;
        return {
            label: upward ? "Height used" : "Length used",
            text: fmt(used) + " of " + fmt(cap) + " in"
        };
    }

    function renderStats() {
        var el = document.getElementById("lpStats");
        var box = currentBox();
        var slider = document.getElementById("lpSlider");
        var total = maxStep();
        if (slider) {
            slider.max = String(total);
            slider.value = String(state.step);
        }
        if (!el) return;
        if (!box) {
            el.innerHTML = "<p>No container was loaded.</p>";
            return;
        }
        var pieces = visible(box);
        var all = ordered(box);
        var volume = 0;
        var weight = 0;
        pieces.forEach(function (item) {
            volume += item.length_in * item.width_in * item.height_in;
            weight += item.weight_lb || 0;
        });
        var cap = box.length_in * box.width_in * box.height_in;
        var cube = cap > 0 ? Math.round(volume / cap * 1000) / 10 : 0;
        var payload = box.max_payload_lb || 0;
        var weightPct = payload > 0 ? Math.round(weight / payload * 1000) / 10 : 0;
        var used = alongUsed(box, all);
        var boxes = (state.result && state.result.containers) || [];
        el.innerHTML = ""
            + "<p class=\"lp-stat-kicker\">Container " + (state.index + 1) + " of " + boxes.length + "</p>"
            + "<h3>" + box.label + "</h3>"
            + "<p><span>Pieces</span><strong>" + pieces.length + " / " + all.length + "</strong></p>"
            + "<p><span>Loaded volume</span><strong>" + fmt(volume / 1728) + " cu ft</strong></p>"
            + "<p><span>Cube</span><strong>" + cube + "%</strong></p>"
            + "<p><span>Loaded weight</span><strong>" + fmt(weight) + " lb</strong></p>"
            + "<p><span>Weight</span><strong>" + weightPct + "%</strong></p>"
            + "<p><span>" + used.label + "</span><strong>" + used.text + "</strong></p>"
            + "<p><span>Step</span><strong>" + state.step + " of " + total + "</strong></p>";
    }

    function syncButtons() {
        document.querySelectorAll("#lpToolbar [data-view]").forEach(function (button) {
            var on = state.quad ? button.getAttribute("data-view") === "quad" : button.getAttribute("data-view") === state.view;
            button.classList.toggle("is-on", on);
        });
        document.querySelectorAll("#lpToolbar [data-style]").forEach(function (button) {
            button.classList.toggle("is-on", button.getAttribute("data-style") === state.style);
        });
        var ids = document.querySelector("#lpToolbar [data-toggle='ids']");
        if (ids) ids.classList.toggle("is-on", state.ids);
        var play = document.querySelector("#lpToolbar [data-toggle='play']");
        if (play) play.textContent = playTimer ? "Pause" : "Play";
        canvas.classList.toggle("is-quad", state.quad);
    }

    function setStep(value) {
        state.step = clamp(value, 0, maxStep());
        renderStats();
        syncButtons();
        draw();
    }

    function stopPlay() {
        if (playTimer) {
            clearInterval(playTimer);
            playTimer = null;
        }
        syncButtons();
    }

    function setView(name) {
        if (name === "quad") {
            state.quad = !state.quad;
            if (!state.quad) state.view = "fl";
        } else {
            state.quad = false;
            state.view = name;
            state.yaw = VIEWS[name].yaw;
            state.pitch = VIEWS[name].pitch;
            state.panX = 0;
            state.panY = 0;
        }
        syncButtons();
        draw();
    }

    function bind() {
        if (bound) return;
        canvas = document.getElementById("lpCanvas");
        if (!canvas) return;
        bound = true;
        var toolbar = document.getElementById("lpToolbar");
        if (toolbar) {
            toolbar.addEventListener("click", function (event) {
                var button = event.target.closest("button");
                if (!button) return;
                var view = button.getAttribute("data-view");
                var step = button.getAttribute("data-step");
                var nav = button.getAttribute("data-nav");
                var toggle = button.getAttribute("data-toggle");
                var style = button.getAttribute("data-style");
                if (view) setView(view);
                if (step === "none") setStep(0);
                if (step === "less") setStep(state.step - 1);
                if (step === "more") setStep(state.step + 1);
                if (step === "all") setStep(maxStep());
                if (nav) {
                    var count = ((state.result && state.result.containers) || []).length;
                    if (!count) return;
                    state.index = (state.index + (nav === "next" ? 1 : -1) + count) % count;
                    state.step = maxStep();
                    renderStats();
                    draw();
                }
                if (toggle === "ids") {
                    state.ids = !state.ids;
                    syncButtons();
                    draw();
                }
                if (toggle === "play") {
                    if (playTimer) {
                        stopPlay();
                        return;
                    }
                    if (state.step >= maxStep()) setStep(0);
                    playTimer = setInterval(function () {
                        if (state.step >= maxStep()) {
                            stopPlay();
                            return;
                        }
                        setStep(state.step + 1);
                    }, 450);
                    syncButtons();
                }
                if (style) {
                    state.style = state.style === style ? "solid" : style;
                    syncButtons();
                    draw();
                }
            });
        }
        var slider = document.getElementById("lpSlider");
        if (slider) {
            slider.addEventListener("input", function () {
                stopPlay();
                setStep(parseInt(slider.value, 10) || 0);
            });
        }
        canvas.addEventListener("pointerdown", function (event) {
            if (state.quad || event.button === 1) return;
            dragging = true;
            panning = event.button === 2 || event.shiftKey;
            lastX = event.clientX;
            lastY = event.clientY;
            try { canvas.setPointerCapture(event.pointerId); } catch (err) { /* synthetic events */ }
            canvas.classList.add("is-dragging");
        });
        canvas.addEventListener("pointermove", function (event) {
            if (!dragging) return;
            var dx = event.clientX - lastX;
            var dy = event.clientY - lastY;
            lastX = event.clientX;
            lastY = event.clientY;
            if (panning) {
                state.panX += dx;
                state.panY += dy;
            } else {
                state.yaw += dx * 0.008;
                state.pitch = clamp(state.pitch - dy * 0.008, -1.2, 1.45);
                state.view = "";
            }
            syncButtons();
            draw();
        });
        function endDrag() {
            dragging = false;
            panning = false;
            canvas.classList.remove("is-dragging");
        }
        canvas.addEventListener("pointerup", endDrag);
        canvas.addEventListener("pointercancel", endDrag);
        canvas.addEventListener("contextmenu", function (event) { event.preventDefault(); });
        canvas.addEventListener("wheel", function (event) {
            event.preventDefault();
            state.zoom = clamp(state.zoom * (event.deltaY > 0 ? 1.08 : 0.92), 0.35, 4);
            draw();
        }, { passive: false });
        document.addEventListener("keydown", function (event) {
            var stage = document.getElementById("lpStage");
            if (!stage || stage.hidden) return;
            if (event.target && event.target.closest && event.target.closest("input, textarea, select")) return;
            if (event.key === "+" || event.key === "=") {
                event.preventDefault();
                setStep(state.step + 1);
            } else if (event.key === "-" || event.key === "_") {
                event.preventDefault();
                setStep(state.step - 1);
            }
        });
        window.addEventListener("resize", resize);
        if (window.ResizeObserver) {
            new ResizeObserver(resize).observe(canvas.parentElement);
        }
        resize();
    }

    window.LpView = {
        show: function (result) {
            bind();
            stopPlay();
            state.result = result || { containers: [] };
            state.index = 0;
            state.step = maxStep();
            state.quad = false;
            state.view = "fl";
            state.yaw = VIEWS.fl.yaw;
            state.pitch = VIEWS.fl.pitch;
            state.zoom = 1;
            state.panX = 0;
            state.panY = 0;
            renderStats();
            syncButtons();
            resize();
        }
    };
})();
