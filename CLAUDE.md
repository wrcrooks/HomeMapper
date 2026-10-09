# HANDOFF: HouseScan — iPhone LiDAR → Floorplan + Home Assistant 3D

> Paste or commit this file as `CLAUDE.md` at the repo root so Claude Code loads it automatically.

## 1. Goal

Build a sideloaded iOS app that scans an **empty house** with Apple **RoomPlan** on an **iPhone 12 Pro (LiDAR)**, plus a **Python post-processor on Linux**. Together they produce:

1. A **dimensionally accurate 2D floorplan**:
   - DXF for CAD.
   - SVG for the Home Assistant `ha-floorplan` card.
2. A **lightweight 3D model** (OBJ + MTL, named objects) for the Home Assistant `floor3d-card`.
3. **Lossless raw scan data** (RoomPlan `CapturedRoom`/`CapturedStructure` JSON + USDZ), so outputs can be regenerated later without rescanning.

The scan is a **one-time job**, so robustness and data capture matter more than polish.

## 2. Hard constraints

| Constraint | Implication |
|---|---|
| Dev machine is **Linux (Debian 12)**; no Mac. | Swift cannot be compiled locally. **All iOS builds run on GitHub Actions macOS runners.** |
| Install path is **Impactor** (Linux, Flathub; fallback: Dadoum/Sideloader) with a **free Apple ID**, over USB via `usbmuxd`. | CI must output an **unsigned `.ipa`**. The sideload tool re-signs it; it expires after 7 days (reinstalling over it keeps app data; deleting the app erases it). The phone needs Developer Mode on. Optional: SideStore for on-device refresh. |
| Xcode project files can't be hand-edited safely without Xcode. | Use **XcodeGen** (`project.yml`). Generate the `.xcodeproj` in CI; never commit it. |
| Device: iPhone 12 Pro. | Deployment target **iOS 17.0**, required for multi-room `StructureBuilder`, `CapturedRoom.floors`, and `sections`. Check `RoomCaptureSession.isSupported` at launch. |
| Files must be retrievable on Linux. | Enable Files-app visibility (`UIFileSharingEnabled`, `LSSupportsOpeningDocumentsInPlace`) and provide a share sheet. **AirDrop doesn't reach Linux**: retrieve via USB (`ifuse --documents <bundle-id>`, libimobiledevice), or share the zip by email/cloud/LocalSend. |

**Claude Code cannot run or compile Swift in this environment. The CI build is the compiler.** Keep changes small, push often, and read CI logs to fix errors. Python tooling *can* be run and tested locally.

## 3. Repo layout (target)

```
housescan/
├─ CLAUDE.md                     # this file
├─ ios/
│  ├─ project.yml                # XcodeGen spec
│  ├─ HouseScan/
│  │  ├─ App/HouseScanApp.swift
│  │  ├─ Capture/                # RoomPlan session + multi-room coordinator
│  │  ├─ Export/                 # USDZ, raw JSON, simplified schema JSON
│  │  ├─ UI/                     # SwiftUI screens
│  │  └─ Info.plist
├─ tools/                        # Python 3.10+, runs on Linux
│  ├─ pyproject.toml
│  ├─ housescan/
│  │  ├─ schema.py               # load/validate simplified JSON
│  │  ├─ geometry.py             # wall merging, snapping, polygon cleanup
│  │  ├─ to_dxf.py               # ezdxf
│  │  ├─ to_svg.py               # ha-floorplan SVG with stable element IDs
│  │  ├─ to_obj.py               # floor3d-card OBJ/MTL, named objects
│  │  └─ calibrate.py            # apply laser-meter check measurements
│  ├─ tests/                     # pytest with fixture JSON
│  └─ fixtures/sample_scan.json  # hand-made 2-room fixture until real data exists
└─ .github/workflows/ios.yml
```

## 4. iOS app spec

### 4.1 Capture flow (multi-room)
- Use `RoomCaptureView` (built-in coaching UI) backed by a single **shared `ARSession`** reused across rooms, so all rooms land in one world coordinate frame.
- For each room:
  1. Start a capture with `RoomCaptureSession.run(configuration:)`.
  2. The user taps "Finish room", which calls `stop(pauseARSession: false)`. Keeping the ARSession alive is critical for alignment.
  3. Receive `CapturedRoom` via `RoomBuilder(options: [.beautifyObjects])`.
  4. Prompt for a **room name** (free text, e.g. "Kitchen", "Primary Bedroom"). Save it alongside the room.
  5. Persist that room's raw data to disk **immediately** (crash safety).
- After the last room, merge all rooms with `StructureBuilder(options: [.beautifyObjects])` into a `CapturedStructure`.
- If the ARSession is lost (app backgrounded, tracking failure), still save each room individually. Merging via `StructureBuilder` across sessions is best-effort; note the failure in the export metadata.

### 4.2 Screens (minimal SwiftUI)
1. **Home**: list of scan projects; a "New scan" button.
2. **Capture**: `RoomCaptureView`, plus buttons for "Finish room", "Next room", and "Done".
3. **Review**: rooms list with wall/door/window counts, a merged-structure status, and Export/Share.
4. **Check measurements** (optional): enter laser-meter values as "label, value (m or ft-in)". Saved to `measurements.json`.

### 4.3 Export bundle (per scan project)
Write to `Documents/<project-name>-<ISO8601>/`:

| File | Content |
|---|---|
| `structure.usdz` | `CapturedStructure.export(to:exportOptions: .parametric)` |
| `structure_mesh.usdz` | Same with `.mesh`, if available (reference only) |
| `rooms/<n>-<slug>.json` | Raw `CapturedRoom`, which is `Codable`, encoded with `JSONEncoder` |
| `rooms/<n>-<slug>.usdz` | Per-room parametric USDZ |
| `structure.json` | Raw `CapturedStructure` (`Codable`) |
| `scan.json` | **Simplified schema** (§5). This is the contract with the Python tools. |
| `measurements.json` | Laser-meter checks, if entered |
| `meta.json` | App version, iOS version, device model, timestamps, merge success/failure, per-room ARKit tracking warnings |

Also offer **"Share all as .zip"** via `UIActivityViewController`.

## 5. `scan.json` simplified schema (the contract)

Units are **meters**. Coordinates use the RoomPlan/ARKit world frame (**Y up**). The Python side projects onto the XZ plane for 2D.

```jsonc
{
  "schema_version": 1,
  "units": "m",
  "up_axis": "Y",
  "rooms": [
    {
      "id": "room-1",
      "name": "Kitchen",
      "section_label": "kitchen",          // from CapturedRoom.sections if present, else null
      "story": 0,
      "floor_polygon": [[x, z], ...],      // from CapturedRoom.floors[].polygonCorners transformed to world; null if absent
      "walls":    [ { "id": "...", "transform": [16 floats, column-major], "dimensions": [w, h, d], "confidence": "high|medium|low" } ],
      "doors":    [ { "id": "...", "parent_wall_id": "...|null", "transform": [...], "dimensions": [...], "is_open": true|null, "confidence": "..." } ],
      "windows":  [ /* same shape as doors, minus is_open */ ],
      "openings": [ /* same shape */ ]
    }
  ]
}
```

Notes:
- RoomPlan surfaces have `transform` (`simd_float4x4`, the center pose) and `dimensions` (`simd_float3`: x = width, y = height, z ≈ 0 for walls). Wall endpoints = center ± (width/2 × local X axis).
- Prefer the **merged `CapturedStructure`** geometry for `scan.json`, so rooms share one frame. Fall back to per-room data if merging failed.
- Use UUIDs from RoomPlan surface `identifier`s for stable IDs.

## 6. Python tools (Linux, locally testable)

Dependencies: `numpy`, `shapely`, `ezdxf`, `svgwrite` (or plain string templating), `pytest`.

CLI: `python -m housescan <scan.json> --out out/ [--measurements measurements.json] [--units ft|m]`

1. **geometry.py**
   - Project walls to 2D segments.
   - Snap near-parallel walls to dominant axes (configurable tolerance, default 2°).
   - Merge collinear, overlapping wall segments from adjacent rooms into shared walls.
   - Build room polygons from `floor_polygon`, or from the wall loop if missing.
2. **calibrate.py**
   - Compare `measurements.json` against the model.
   - Report per-measurement error.
   - Optionally apply a global uniform scale with `--apply-scale`. Never apply it silently.
3. **to_dxf.py**
   - Layers: `WALLS`, `DOORS` (with swing arcs), `WINDOWS`, `ROOMS` (polylines plus name and area text), `DIMENSIONS`.
   - Units set in the header.
4. **to_svg.py** (for `ha-floorplan`)
   - Every room is a `<path id="area.<slug>">` and every door/window gets a stable `id`, so HA CSS rules can target them.
   - Walls go in a separate group; viewBox in cm.
   - No fill on room paths by default.
5. **to_obj.py** (for `floor3d-card`)
   - Extrude walls to their measured height, cut door and window openings (`shapely` difference on the wall's elevation profile), and add a floor slab per room.
   - **One named OBJ object per element** (`wall_<id>`, `door_<id>`, `window_<id>`, `floor_<roomslug>`), because floor3d-card binds entities by object name.
   - Separate MTL materials per element type.
   - Y-up, meters.
6. Write `report.md` summarizing room areas, wall count, calibration errors, and warnings.

## 7. CI: `.github/workflows/ios.yml`

- Trigger: push to `main` + `workflow_dispatch`.
- Runner: latest `macos-*` image with Xcode supporting the iOS 17+ SDK.
- Steps:
  1. `brew install xcodegen`, then `cd ios && xcodegen generate`.
  2. `xcodebuild -project HouseScan.xcodeproj -scheme HouseScan -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -archivePath build/HouseScan.xcarchive archive CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY=""`
  3. Package: `mkdir Payload && cp -r build/HouseScan.xcarchive/Products/Applications/HouseScan.app Payload/ && zip -r HouseScan.ipa Payload`
  4. `actions/upload-artifact` → `HouseScan.ipa`.
- Separate job (ubuntu): `pytest tools/`.
- macOS runner minutes are billed at a premium on private repos. Use a public repo, or keep pushes batched.

## 8. Info.plist / project.yml essentials
- `NSCameraUsageDescription`: "Used to scan rooms with LiDAR."
- `UIFileSharingEnabled` = YES and `LSSupportsOpeningDocumentsInPlace` = YES.
- `UIRequiredDeviceCapabilities`: `arkit`.
- Bundle ID: unique reverse-DNS (e.g. `local.<user>.housescan`). The sideload tool may rewrite it.
- Frameworks: `RoomPlan`, `ARKit`, `RealityKit`.
- Portrait-only is fine.

## 9. Implementation phases & acceptance criteria

| Phase | Deliverable | Done when |
|---|---|---|
| **0** | XcodeGen skeleton + CI producing an `.ipa` from a "Hello" SwiftUI app | Artifact downloads, installs via Impactor, launches on device |
| **1** | Single-room capture + raw JSON + USDZ export + share sheet | A room scans and the files appear in the Files app on the iPhone |
| **2** | Multi-room shared ARSession + `StructureBuilder` merge + room naming + `scan.json` + `meta.json` | Two adjacent rooms export into one frame; their shared wall lines up within ~3 cm |
| **3** | Python: schema, geometry, DXF, SVG, report + pytest on the fixture | `pytest` green; DXF opens in a free CAD viewer; SVG renders in a browser |
| **4** | Python: OBJ/MTL + calibrate | OBJ loads in floor3d-card with named objects; calibration report lists errors |
| **5** | Measurement-entry screen, polish, crash-safe autosave | Real whole-house scan exported end-to-end |

Work phase by phase. **Phase 0 first:** the build/sideload pipeline is the highest risk and must be proven before any RoomPlan code.

## 10. Known risks / guidance
- **Drift:** RoomPlan is accurate within a room (~1–2 cm), but stitched rooms can drift several cm across a house. Mitigations: one continuous ARSession, ending the walk where it began, and the calibration step with laser-meter check measurements on long runs.
- **Glass/mirrors** confuse LiDAR. Coaching text should tell the user to close blinds and cover mirrors.
- **Interior doors open** during scanning helps continuity.
- Treat RoomPlan **confidence** as data. Flag `low` surfaces in the report rather than dropping them.
- Do not depend on private APIs or a jailbreak.
- Before using newer RoomPlan APIs, confirm their iOS availability (e.g. `sections`, `floors`, `StructureBuilder` are iOS 17+) and wrap them in `if #available`.

## 11. Out of scope (for now)
- Furniture/object export (the house is empty).
- Auto-generating Sweet Home 3D `.sh3d` files. A possible later phase: `.sh3d` is a zip containing `Home.xml`, so it could be generated from `scan.json`.
- Texture/photo capture.
- Direct HA integration. The output is static files the user copies into `/config/www/`.

## 12. First task for Claude Code
1. Create the repo layout above.
2. Write `ios/project.yml`, a minimal SwiftUI app, and `.github/workflows/ios.yml` (Phase 0).
3. Write `tools/` scaffolding with `fixtures/sample_scan.json` (two rooms sharing a wall, one door, one window) and failing tests for `geometry.py`.
4. Stop and report the CI result before starting Phase 1.
