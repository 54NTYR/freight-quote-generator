# Load Planning domain

Jericho Freight module. The screen title is Load Planning. This is not Cube-IQ. The decompiled Cube-IQ 5 help was used only as a product, UX, and domain spec. The packer and the screens are original.

## Vocabulary

Cube-IQ uses two words for everything that gets loaded and everything that holds it.

| Cube-IQ word | Meaning | Jericho name |
|---|---|---|
| Product | SKU, carton, pallet, drum, or other cargo item | Product |
| Container | Ocean box, truck or trailer, pallet, ULD, carton, crate, or railcar | Container |
| Load | One planning case: containers available, products and quantities, then an optimized result | Plan |

A product is not a freight rate. A container is not a drayage equipment code. Those catalogs stay on their own screens.

## Units (v1)

Inches and pounds only. Cube-IQ can switch cm, m, mm, inch, ft, and lbs, kg, tonnes per record. Mixed units and live conversion are deferred. Volume on screen is cubic feet (`cu in / 1728`) plus a cube percent.

## Coordinate system

Origin is the nose, left wall, and floor. That matches Cube-IQ's back-left-lower corner. Cube-IQ's "back" is the nose of a truck (the end opposite the door).

| Axis | Zero | Increases toward |
|---|---|---|
| x (length) | Nose | Door |
| y (width) | Left wall | Right wall |
| z (height) | Floor | Ceiling |

A placement `(x, y, z)` is the nose-left-floor corner of that piece after rotation. Upright keeps the product's length on x, width on y, and height on z. "Turned on floor" swaps length and width and leaves height upright.

Load direction:

- `back_to_front` (trailers and ocean boxes): prefer the nose, then the floor, then the left wall.
- `bottom_to_top` (pallets and cartons): prefer the floor, then the nose, then the left wall.

## Workflow

1. Keep container and product masters (entered once, reused).
2. Create a plan.
3. Choose container types and how many are available.
4. Choose products and quantities.
5. Optimize.
6. Read utilization, the 2D plan, and leftovers. Change quantities and optimize again.
7. Print the plan or export JSON.

## v1 entities

### Product

id, name, length, width, height, weight, quantity on the plan, turn-on-floor (upright is always allowed), stackable, max stack, on floor only, on top only, supported weight (blank means not checked), stack index (blank means not checked), notes, color.

Shape is a rectangular box. Rolls, sofas, T-shapes, and tapered boxes are deferred.

Orientations in v1:

- Upright.
- Turned on the floor (yaw 90 degrees) when allowed.

The other four tip orientations (on side, on end, and their yaws) are not offered. Per-orientation rule rows are deferred. The flags above apply to the whole product.

### Container

id, label, type (`truck`, `ocean`, `pallet`, `box`, `railcar`, `rectangular`), interior length, width, height, max payload, load direction.

Seeded interiors (editable): 53 ft dry van, 48 ft dry van, 40 ft high cube, 20 ft standard, 48 x 40 pallet. These are typical interiors, not a measured trailer.

Unusable spaces can be stored later. v1 does not keep cargo out of them. If a payload includes them, the plan warns that they were not applied.

### Plan

Optional customer (same customer list as quotes), selected containers with available counts, product lines with quantity, placements, metrics, leftovers, notes, plan number, date.

Plan numbers are `PLAN-Q###` from a local counter (`plan_counter.json`). They do not call the shared Google quote counter, so FTL, LTL, Dray, and International numbers stay on their own sequence. The Google script stores one number for every mode and only logs the mode code.

## v1 rules the packer enforces

- Stay inside the interior box.
- No overlapping boxes. Faces may touch.
- Do not exceed payload weight.
- Upright, plus turn-on-floor when allowed.
- Not stackable: nothing may sit on that piece.
- Max stack: how many of that same product may sit in one vertical column.
- On floor only: on the floor, or on the same product.
- On top only: a different product may not sit on it. The same product may, up to max stack.
- Supported weight, when set: weight resting on that piece cannot exceed it. Weight of a piece that spans two supporters is split by overlap area.
- Stack index, when both pieces have one: the upper index must be less than or equal to the lower index (a lower index is loaded higher).
- A piece above the floor needs support under at least 75% of its footprint.
- Deterministic. No random step. The same input places the same way.
- More than one container: fill the first, then the next available copy, then the next type. Pieces that never fit are leftovers with a plain message.
- Metrics: cube percent, weight percent, loaded count versus ordered count, per container and for the plan.

The packer is a bottom-left fill. It tries nose-left-floor corners of boxes already placed and keeps the first corner that satisfies the rules, in load-direction order. It is not a copy of any Cube-IQ solver.

## Deferred (hooks only)

| Topic | Why it waits |
|---|---|
| Six custom orientations, each with its own on-floor, on-top, max stack, supported weight, and stack index | v1 uses two orientations and one rule set per product |
| Stack codes and the stacking matrix | One stack index plus the flags above cover the basic case |
| Combination codes and the combination matrix | No "may not ride with" rules yet |
| Configurations (each, case, pallet of the same SKU) | A pallet is its own product or its own container for now |
| Axle weights and center-of-gravity targets | No bridge formula in v1 |
| Unusable spaces, irregular floor and ceiling, zones, outside dimensions | Rectangular interior only. Warning if unusable spaces are sent |
| Pallet layer rules, overhang, center load, mixed layers | Pallet containers only change load direction to floor-first |
| Fill percent minimum and maximum, container sizing | Utilization is reported, not used as a hard reject |
| Optimizer time limits and iteration caps | The fill is a single deterministic pass |
| Gap between pieces, reach, drop walls | Pieces may touch |
| Drop sequence, groups, PO grouping, spread sequence 0 | One sequence: placement order from the nose or the floor |
| Multi-stage (cartons on pallets, pallets on a truck) | One stage |
| Fixing part of a load and drag editing | Print and re-optimize. No 3D editor |
| Rolls and non-box shapes | Boxes only |
| Excel, CSV, XML import and export | JSON export of one plan |
| Per-record unit conversion | Inches and pounds |
| Customer matching codes, shipping cost, container selection by lowest cost | The user picks the containers |
| Manifest as a separate report, logos, translation | One printable plan |
| Shared Google number for plans | Would consume the next FTL/LTL/Dray/International number |

## Persistence

SQLite tables `lp_products`, `lp_containers`, and `lp_plans` in the same history database. Migrations are `CREATE TABLE IF NOT EXISTS` only. Plans reload from stored JSON. Product and container masters are independent of terminal locations.
