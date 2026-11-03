---
name: Simu-Emperor
description: Simple light historical-cartographic court strategy interface with EU4 spatial layout and georeferenced jiangshan-map atlas canvas.
colors:
  accent-cinnabar: "#9e3a2e"
  accent-cinnabar-hover: "#8b3126"
  accent-cinnabar-bg: "rgba(158, 58, 46, 0.08)"
  accent-ochre: "#b87328"
  accent-ochre-bg: "rgba(184, 115, 40, 0.10)"
  accent-sage: "#587854"
  accent-sage-bg: "rgba(88, 120, 84, 0.10)"
  accent-slate: "#7a7067"
  bg-atlas-canvas: "#eae2d3"
  bg-ocean-paper: "#e5decb"
  surface-panel: "rgba(250, 247, 242, 0.96)"
  surface-panel-solid: "#faf7f2"
  surface-subtle: "#f2ece1"
  surface-hover: "#eae2d3"
  surface-disabled: "#e2dcd0"
  border-hairline: "#dcd4c6"
  border-row-divider: "#eae3d5"
  border-strong: "#c2b8a6"
  border-disabled: "#d2cabd"
  ink-primary: "#1f1c18"
  ink-secondary: "#685f54"
  ink-muted: "#8c8275"
  ink-disabled: "#766d61"
  pure-white: "#ffffff"
typography:
  display:
    fontFamily: "Songti SC, STSong, Noto Serif SC, Source Han Serif SC, serif"
    fontSize: "27px"
    fontWeight: 700
    lineHeight: 1.15
  headline:
    fontFamily: "Songti SC, STSong, Noto Serif SC, Source Han Serif SC, serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.35
  title:
    fontFamily: "Songti SC, STSong, Noto Serif SC, Source Han Serif SC, serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "PingFang SC, Hiragino Sans GB, Microsoft YaHei, Noto Sans SC, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "PingFang SC, Hiragino Sans GB, Microsoft YaHei, Noto Sans SC, sans-serif"
    fontSize: "13.5px"
    fontWeight: 600
    lineHeight: 1.35
rounded:
  xs: "4px"
  sm: "5px"
  md: "6px"
  lg: "7px"
  xl: "9px"
  pill: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
components:
  button-primary:
    backgroundColor: "{colors.accent-cinnabar}"
    textColor: "{colors.pure-white}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
  button-primary-hover:
    backgroundColor: "{colors.accent-cinnabar-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.surface-disabled}"
    textColor: "{colors.ink-disabled}"
  button-secondary:
    backgroundColor: "{colors.surface-panel-solid}"
    textColor: "{colors.ink-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
  button-outline-cinnabar:
    backgroundColor: "{colors.surface-panel-solid}"
    textColor: "{colors.accent-cinnabar}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
  timeline-step-pill:
    backgroundColor: "{colors.surface-panel-solid}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "5px 12px"
  drawer-tab:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.title}"
    padding: "12px 6px 13px"
  outliner-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink-primary}"
    typography: "{typography.title}"
    rounded: "{rounded.md}"
    padding: "9px 10px"
  decision-radio-pill:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.ink-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "5px 10px"
  chat-input:
    backgroundColor: "{colors.surface-panel-solid}"
    textColor: "{colors.ink-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "7px 10px"
  map-layer-switcher:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.lg}"
    padding: "3px"
  floating-sheet-card:
    backgroundColor: "{colors.surface-panel}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.xl}"
    width: "404px"
---

# Design System: Simu-Emperor

## Overview

**Creative North Star: "Simple cartographic interface"**

Simu-Emperor uses a simple light historical-cartographic interface where Paradox EU4 supplies the spatial layout only and the visual language is adapted from DeanChensj/jiangshan-map (commit a9cd67c). A continuous full-viewport (100vw × 100vh) SVG map serves as the primary workspace, layering georeferenced shaded relief (terrain_relief.webp), modern reference provincial and coastline boundaries, ranked blue hydrography, and low-opacity multiply watercolor washes across three fictional playable jurisdictions (甲州, 乙州, 丙州) and surrounding non-playable background geography.

Floating UI chrome is kept light and restrained so geography remains dominant. A compact top-left floating resource bar, an independent top-right date and turn-action box aligned above the right state outliner, a closable 404px left state sheet, and a compact lower-right map control dock sit on warm ivory panels (rgba(250, 247, 242, 0.96)) separated by 1px stone hairlines (#dcd4c6) and row dividers (#eae3d5), leaving a continuous visible map expanse across the top center. Classical Chinese Songti (--font-serif-cn) carries state titles, top treasury and calendar date figures, sheet tabs, report key-value rows, outliner rows, and map annotations, while clean sans-serif (--font-sans-cn) handles operational buttons, dropdown menus, chat streams, and form controls. Cinnabar (#9e3a2e) marks active selection and primary actions. The system rejects ornate gilded frames, heraldic crests, fantasy illustrations, dark slate chrome, and middle-dot (`·`) text separators.

**Key Characteristics:**
- Full-viewport (100vw × 100vh) georeferenced SVG map adapted from DeanChensj/jiangshan-map with Mercator projection, shaded relief (terrain_relief.webp at 0.72 opacity), ranked blue rivers and lakes, and 2D occlusion-aware SVG viewBox camera math.
- EU4-inspired corner-anchored spatial layout (compact top-left floating resource bar with gear utility menu, top-right independent date and turn-action box aligned above the right state outliner, closable left state sheet, lower-right map layer and camera controls) rendered in flat warm ivory panels with continuous map visibility between top-left and top-right.
- Presentation-only UTC weekly calendar (`1444-11-11` for Week 1, `+7` UTC days per week) derived strictly from server week (`current_active_week` or `viewed_week` in history view) with a `往期` dropdown for available dated weeks.
- Strict report-only visual encoding across disaster, grain, and silver layers using multiply watercolor washes (urgent cinnabar #b54434, mild ochre #c88a3b, stable sage #7a9a76) and a 45-degree slate diagonal hatch for unreported (UNKNOWN) states.
- Dual-type hierarchy pairing classical Songti serif (--font-serif-cn) for editorial headings, calendar dates, tabs, key-value report rows, outliner summaries, and map labels with neutral sans-serif (--font-sans-cn) for operational controls and chat.
- Responsive adaptation across 1586×992, 1440×900 (<=1460px), 1280×800 (<=1320px), and 390×844 mobile (<=960px), where the left sheet becomes an opaque full-width pane that suppresses background map bleed while open.

## Colors

The palette pairs warm rice-paper and ivory grounds with dark warm-ink typography and four restrained mineral accents that encode both UI state and report-only map severity.

### Primary
- **Cinnabar Accent** (`--accent-cinnabar`, `#9e3a2e`): Primary interactive accent used for active phase buttons (`截止征询`, `批复结算`), chat submission (`发旨`), active tab underlines (`2.5px solid`), active week/layer/channel pill borders, focus rings (`2px solid`), urgent report status values (`洪灾`, `存粮匮乏`, `存银匮乏`), and `UNKNOWN` warning text (`本周未奏报（未知）`).
- **Cinnabar Deep Hover** (`--accent-cinnabar-hover`, `#8b3126`): Hover state fill for primary cinnabar action buttons (`.court-action-btn.is-primary-cinnabar:hover`, `.primary-court-btn:hover`).
- **Cinnabar Wash Tint** (`--accent-cinnabar-bg`, `rgba(158, 58, 46, 0.08)`): Soft background tint for hover states on cinnabar outline buttons, `拟驳回` radio pills (`.radio-pill.selected-reject`), inline error banners, and `UNKNOWN` top source pills.

### Secondary
- **Ochre Warning Accent** (`--accent-ochre`, `#b87328`): Secondary semantic accent used for mild disaster/shortage statuses (`旱灾`, `存粮偏紧`, `存银偏紧`), incomplete approval draft counts (`.draft-status-tag.incomplete`), late chat reply notices, `@` mention indicators, history-return buttons (`.top-return-current-btn`), and Debug Truth badges/headers.
- **Ochre Wash Tint** (`--accent-ochre-bg`, `rgba(184, 115, 40, 0.10)`): Subtle warm tint for Debug Truth comparison cards (`.debug-truth-card`), phase hint strips (`.phase-hint-strip`), and history read-only notices.

### Tertiary
- **Sage Stable Accent** (`--accent-sage`, `#587854`): Semantic accent for stable/abundant state reports (`无灾`, `平稳`, `存粮充裕`, `存银充裕`), completed approval draft readiness (`.draft-status-tag.ready`), `拟批准` radio pills (`.radio-pill.selected-approve`), and the four-week trial completion badge (`.trial-completed-status`).
- **Sage Wash Tint** (`--accent-sage-bg`, `rgba(88, 120, 84, 0.10)`): Soft fill for selected `拟批准` decision radio pills.
- **Slate Unknown Accent** (`--accent-slate`, `#7a7067`): Neutral-cool mineral gray for unreported (`unknown`) state indicator dots (`.pill-dot.dot-unknown`), unreported territory borders, and diagonal hatch strokes.

### Neutral
- **Atlas Rice-Paper Canvas** (`--bg-atlas-canvas`, `#eae2d3`): Root application background and map viewport base ground.
- **Ocean Rice-Paper Ground** (`--bg-ocean-paper`, `#e5decb`): Base SVG sea fill (`.map-ocean-bg`) and edge-fade gradient stop (`#terrain-fade-h`, `#terrain-fade-v`) blending the shaded relief raster into the surrounding paper.
- **Floating Ivory Panel** (`--surface-panel`, `rgba(250, 247, 242, 0.96)`): Translucent warm ivory surface for desktop floating chrome (`.court-top-bar`, `.left-court-sheet`, `.right-court-outliner`, `.map-layer-pill-group`, `.map-legend-card`).
- **Solid Ivory Surface** (`--surface-panel-solid`, `#faf7f2`): Opaque ivory surface used for buttons, timeline pills, chat bubbles, proposal line items, modal cards, floating banners, and the full-width mobile state sheet (`<=960px`).
- **Subtle Warm Stone** (`--surface-subtle`, `#f2ece1`): Secondary container fill for chat message streams, proposal cards, central budget cards, unselected channel/radio pills, and button hover states.
- **Warm Hover Surface** (`--surface-hover`, `#eae2d3`): Hover fill for compact header state pills.
- **Disabled Surface & Border** (`--surface-disabled` `#e2dcd0`, `--border-disabled` `#d2cabd`, `--ink-disabled` `#766d61`): Solid muted stone tokens applied at `opacity: 1` to disabled action and primary CTA buttons so disabled controls maintain legible contrast.
- **Stone Hairlines & Dividers** (`--border-hairline` `#dcd4c6`, `--border-row-divider` `#eae3d5`, `--border-strong` `#c2b8a6`): `1px` structural borders separating floating panels (`#dcd4c6`), internal key-value and outliner rows (`#eae3d5`), and interactive button/input/divider strokes (`#c2b8a6`).
- **Warm Ink Hierarchy** (`--ink-primary` `#1f1c18`, `--ink-secondary` `#685f54`, `--ink-muted` `#8c8275`, `--pure-white` `#ffffff`): Primary body and title ink (`#1f1c18`), secondary metadata and unselected tab/pill ink (`#685f54`), muted chevron and hint ink (`#8c8275`), and crisp white text on solid cinnabar buttons (`#ffffff`).
- **Cartographic Map Layer Fills & Hydrography**: Territory washes in `web/components/MapViewport.tsx` render at `fill-opacity: 0.30` (`0.36` selected, `0.38` hover) with `mix-blend-mode: multiply` using `#B54434` (urgent), `#C88A3B` (mild), `#7A9A76` (stable), and `#9A9488` (unknown) paired with `#8C2D22` selected borders (`#8F3628` / `#946528` / `#586F54` / `#7A7067` unselected). Ranked hydrography uses muted mineral blues (`rgba(36, 102, 136, 0.90)` trunk rivers `1.7px`, `rgba(48, 114, 146, 0.82)` major rivers `1.2px`, `rgba(66, 128, 158, 0.66)` medium rivers `0.88px`, `rgba(94, 144, 168, 0.44)` minor rivers `0.56px`, and `rgba(82, 150, 184, 0.70)` major lakes) cased in warm paper (`rgba(246, 239, 225, 0.48)`).

## Typography

**Display Font:** `"Songti SC", "STSong", "Noto Serif SC", "Source Han Serif SC", serif` (`--font-serif-cn`)
**Body Font:** `"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif` (`--font-sans-cn`)

**Character:** Classical Chinese Songti serif gives court-memorial authority to state titles, treasury figures, navigation tabs, key-value ledger rows, outliner rows, and map cartography, while clean system sans-serif keeps operational buttons, timeline pills, chat threads, and form inputs crisp and fast to scan. Numeric metrics enforce `font-variant-numeric: tabular-nums` so silver (`万两`) and grain (`万石`) figures align across rows.

### Hierarchy
- **Display** (`700`, `27px` default / `24px` at `<=1320px` / `21px` at `<=960px`, `line-height: 1.15`, `--font-serif-cn`): Selected state title (`.sheet-state-title`) anchoring the top-left of the state sheet.
- **Headline** (`700`, `17px` default / `16px` at `<=1460px` / `14px` at `<=1320px`, `line-height: 1.35`, `--font-serif-cn`): Top bar central treasury values (`.treasury-value`), memorial summary heading (`.summary-title`), and modal dialog titles (`.court-modal-card h3`).
- **Title** (`600`–`700`, `16px`–`16.5px` default / `15px`–`15.5px` at `<=1320px` / `14.5px` at `<=960px`, `line-height: 1.4`, `--font-serif-cn`): Right outliner header (`.outliner-header`, `16.5px`, `700`), sheet tab labels (`.drawer-tab-btn`, `16px`, `600` default / `700` active), report key-value labels (`.sheet-kv-row dt`, `16px`, `600`), report key-value figures (`.kv-val` and `.kv-main-num`, `16.5px`, `700`), and outliner state rows (`.outliner-state-row`, `15px` state name, `14px` summary).
- **Body** (`400`–`600`, `15px` default / `14px`–`14.5px` compact, `line-height: 1.5`–`1.78`, `--font-sans-cn`): Base document text (`15px`), memorial summary paragraph (`.report-summary-box`, `15px`, `line-height: 1.78`, `14px` at `<=1320px`), sheet footer action buttons (`15px`, `600`), and chat message content (`.bubble-content`, `14px`, `line-height: 1.55`).
- **Label** (`500`–`700`, `12px`–`13.5px`, `line-height: 1.35`, `--font-sans-cn`): Top HUD action/utility buttons and week timeline step pills (`13.5px`, `13px` at `<=1460px`, `11.5px`–`12px` at `<=1320px`), sheet header subtitle (`13.5px`), channel selector pills (`13px`), approval decision radio pills (`13px`, `600`), legend items (`13px`), and source/debug metadata pills (`11.5px`–`12.5px`).
- **Cartographic SVG Labels** (`--font-serif-cn` and `--font-sans-cn`, scaled dynamically by `labelScale = 1 / sqrt(clamp(zoom, 0.65, 2.6))` with `paint-order: stroke fill` warm-paper halos): Playable state titles (`.map-state-title`, `6.6px`, `700`, `letter-spacing: 0.14em`), regional land/sea captions (`.map-regional-caption`, `5.0px`, `600`, `letter-spacing: 0.26em`–`0.30em`), prefecture seat labels (`.map-seat-label`, `3.3px`, `600`), state status sub-captions (`.map-state-sub-caption`, `3.2px`, `600`, `--font-sans-cn`), river captions (`.hydro-label`, `3.0px`, `italic`, `600`), and secondary town labels (`.map-town-label`, `2.95px`, `500`, visible when `zoom >= 0.8`).

## Layout

The interface uses a full-viewport map canvas (`100vw × 100vh`, `overflow: hidden`) with an EU4-inspired corner-anchored floating overlay on desktop and a single-column flex stack on narrow screens:

1. **Full-Viewport Cartographic Workspace (`.simu-emperor-shell` > `.court-main-workspace` > `.map-viewport`)**:
   - Occupies `position: absolute; inset: 0; width: 100%; height: 100%` at `z-index: 1`.
   - Renders `<svg class="strategy-map-svg" preserveAspectRatio="xMidYMid slice">` with base viewBox dimensions `460 × 288` (`MAP_VIEWBOX_ORIGIN_X = 395`, `MAP_VIEWBOX_ORIGIN_Y = 278`).
   - **2D Occlusion-Aware Camera Corridor (`computeMinimalOcclusionPan`)**: Selecting a playable state from the map or outliner checks whether the state's projected center sits inside the unobstructed map corridor between the floating panels (`34%` to `74%` of viewport width horizontally, `18%` to `78%` of viewport height vertically). If occluded, the camera pans the minimal distance required to place the state center at `44%` (left sheet clearance) or `65%` (right outliner clearance) horizontally and `28%` (top HUD clearance) or `68%` (bottom controls clearance) vertically, without altering zoom.
2. **Top-Left Compact Resource & Utility Bar (`.court-top-bar`, `z-index: 30`)**:
   - Anchored at `top: 16px; left: 18px` with `display: inline-flex; align-items: center`, leaving the top-center map canvas unobstructed.
   - Displays reported central treasury metrics (`朝廷存银`, `|`, `朝廷存粮`, optional debug truth pill), paired with `同步`, conditional `展开奏报`, and an authored SVG gear button opening a popover utility menu (`调试真值视图`, `君主访问凭据`).
3. **Top-Right Date & Turn-Action Stack (`.right-hud-stack` > `.court-date-turn-box` + `.right-court-outliner`, `z-index: 30`)**:
   - Anchored at `top: 16px; right: 18px; width: 376px`, stacking the independent date and turn-action card (`.court-date-turn-box`) directly above the right state outliner (`.right-court-outliner`) with `gap: 12px`.
   - `.court-date-turn-box` features a two-row layout: top row with the server-derived UTC calendar date (`1444年11月11日` for Week 1, `+7` UTC days per week, `31px` / `28px` / `23px` Songti) and `往期` disclosure panel (listing only available dated weeks `1 .. current_active_week`); bottom row with the two-step court workflow buttons (`截止征询` and `下一回合`, or `返回当前` in history view, or `试玩结束` when Week 4 is archived).
4. **Closable Left State Sheet (`.left-court-sheet`, `z-index: 25`)**:
   - Anchored at `top: 76px; left: 18px; width: 404px; max-height: calc(100vh - 96px)`.
   - Header displays the selected state title (`乙州`), narrow-screen state switcher pills, and an SVG close icon button.
   - On the `本州奏报` tab (`.left-court-sheet.is-tab-report`), enforces `min-height: min(702px, calc(100vh - 96px))` so the 5 key-value rows (`灾情状态`, `可支配存粮`, `可支配存银`, `本州赈灾需求`, `向朝廷请拨`), `奏折摘要` section, and 2-column footer button bar (`传讯官员`, `审阅提案`) maintain balanced vertical proportion.
5. **Concise Right State Outliner (`.right-court-outliner`)**:
   - Width-aligned inside `.right-hud-stack` (`padding: 14px 16px`), stacking the `各州奏报` header and 3 single-line 3-column state status rows (`甲州` | `无灾` | `请银1.0万两`) using alignment rather than middle-dot punctuation.
6. **Lower-Right Map Controls & 5-State Legend (`.map-bottom-right-controls`, `z-index: 20`)**:
   - Anchored at `right: 18px; bottom: 18px`, right-aligned in two rows (`gap: 9px`): top row with the 3-pill layer switcher (`灾情`, `存粮`, `存银`) and camera buttons (`+`, `−`, `复位视图`); bottom row with the 5-state legend card (`gap: 14px; padding: 7px 14px`).
7. **Responsive Breakpoints (`web/styles.css`)**:
   - **Default Desktop (`>1460px`, validated at `1586×992`)**: Top-left HUD `top: 16px`, `left: 18px`, `min-height: 44px`; Left sheet `top: 76px`, `left: 18px`, `width: 404px`, report `min-height: 702px`; Right HUD stack `top: 16px`, `right: 18px`, `width: 376px`, date `31px`.
   - **Medium Desktop (`@media (max-width: 1460px)`, validated at `1440×900`)**: Top-left HUD `top: 14px`, `left: 16px`, `min-height: 44px`; Left sheet `top: 68px`, `left: 16px`, `width: 386px`, report `min-height: min(684px, calc(100vh - 86px))`; Right HUD stack `top: 14px`, `right: 16px`, `width: 352px`, date `28px`.
   - **Compact Desktop (`@media (max-width: 1320px)`, validated at `1280×800`)**: Top-left HUD `top: 12px`, `left: 14px`, `min-height: 40px`; Left sheet `top: 62px`, `left: 14px`, `width: 360px`, report `min-height: min(636px, calc(100vh - 78px))`; Right HUD stack `top: 12px`, `right: 14px`, `width: 304px`, date `23px`.
   - **Mobile / Narrow Viewport (`@media (max-width: 960px)`, validated at `390×844`)**: `.court-main-workspace` switches to `display: flex; flex-direction: column; padding: 6px; gap: 6px`. `.court-top-bar` and `.court-date-turn-box` become compact full-width header cards at the top of the flex stack while `.right-court-outliner` hides (`display: none`) and `.state-pill-selector` (`甲`, `乙`, `丙` pills) appears inside `.left-sheet-header`. `.left-court-sheet` becomes `position: relative; flex: 1; width: 100%; max-height: none; background: var(--surface-panel-solid)`, `.chat-messages-stream` expands (`max-height: none; flex: 1`), touch targets on tabs and footer CTAs expand to `min-height: 44px`, and `.map-viewport.is-drawer-open` sets `visibility: hidden; pointer-events: none` on `.map-camera-stage` and `.map-bottom-right-controls` so map graphics never bleed behind the open sheet.

## Elevation & Depth

Depth is established primarily through warm tonal layering (`#eae2d3` canvas -> `#f2ece1` subtle wells -> `#faf7f2` ivory cards) and `1px solid` stone hairlines (`#dcd4c6`), reinforced by low-opacity warm-ink ambient shadows on floating map overlays. Top HUD bars, internal key-value rows, chat bubbles, and proposal cards remain completely flat (`box-shadow: none`).

### Shadow Vocabulary
- **Left State Sheet Shadow** (`box-shadow: 0 4px 16px rgba(31, 28, 24, 0.06)`): Soft ambient lift on `.left-court-sheet` separating the primary inspection panel from the terrain relief canvas.
- **Right Outliner Shadow** (`box-shadow: 0 3px 12px rgba(31, 28, 24, 0.05)`): Subtle elevation on `.right-court-outliner`.
- **Map Control Dock Shadow** (`box-shadow: 0 2px 8px rgba(31, 28, 24, 0.04)`): Low-profile lift on `.map-layer-pill-group`, `.map-zoom-btn`, `.map-reset-btn`, and `.map-legend-card`.
- **Floating Alert Banner Shadow** (`box-shadow: 0 4px 12px rgba(31, 28, 24, 0.08)`): Elevated alert shadow on `.court-floating-banner` (`z-index: 40`).

## Shapes

The form language uses crisp, low-radius rectangles framed by `1px solid` warm stone borders, paired with organic Mercator-projected geographic contours on the map canvas:

- **Panel & Card Radii**: Floating primary panels (`.left-court-sheet`, `.right-court-outliner`) use `9px` (`rounded.xl`). Modal cards use `8px`. Map control groups and legend cards use `7px` (`rounded.lg`). Buttons, outliner rows, chat streams, chat bubbles, textareas, and proposal cards use `6px` (`rounded.md`). Timeline pills, top bar buttons, channel pills, and decision radio pills use `5px` (`rounded.sm`). Compact state pills, mention chips, and debug badges use `4px` (`rounded.xs`). Top bar source pills use `12px` (`rounded.pill`).
- **Hairline & Divider Architecture**: Panels are bounded by `1px solid #dcd4c6` (`--border-hairline`). Report key-value rows (`.sheet-kv-row`) and outliner state rows (`.outliner-state-row`) use `1px solid #eae3d5` (`--border-row-divider`) bottom borders rather than nested card boxes. Interactive buttons and form inputs use `1px solid #c2b8a6` (`--border-strong`).
- **Cartographic Boundary & Selection Geometry**: All SVG strokes set `vector-effect: non-scaling-stroke`. Background provincial boundaries combine a `2.05px` light paper casing (`rgba(250, 245, 234, 0.54)`), `0.96px` dashed interior borders (`stroke-dasharray: 4.5 2.2`, `rgba(70, 56, 42, 0.62)`), and `1.05px` solid outer coastlines (`rgba(64, 50, 38, 0.64)`). Playable state borders use a `2.4px` paper casing under a `1.35px` dashed stroke (`stroke-dasharray: 4.5 2.0`) and `0.85px` dashed internal sub-boundaries (`stroke-dasharray: 3.5 2.2`). The active selected state overlays a `3.6px` paper halo (`rgba(250, 247, 242, 0.82)`) and a solid `2.1px` cinnabar border (`#8c2d22`).

## Components

### Buttons
Action buttons use concise Chinese labels, `1px solid` borders, and `120ms ease` transitions without decorative unicode symbols or gradients.
- **Shape:** `6px` radius (`rounded.md`) on sheet and modal buttons; `5px` radius (`rounded.sm`) on compact top HUD bar and date-turn card buttons.
- **Primary:** Solid cinnabar background (`#9e3a2e`), matching border (`#9e3a2e`), pure white text (`#ffffff`), `font-size: 15px` (`13.5px` in top/turn bars), `font-weight: 600`, `padding: 10px 14px` (`6px 12px` in turn bar). Used for `截止征询` (when `OPEN`), `下一回合` (when `LOCKED` and draft ready), `发旨`, and modal submit CTAs.
- **Hover / Focus:** Primary hover deepens to `#8b3126`; secondary hover shifts from `#faf7f2` to `#f2ece1`; cinnabar outline hover tints with `rgba(158, 58, 46, 0.08)`. Keyboard `:focus-visible` renders `outline: 2px solid #9e3a2e; outline-offset: 2px`.
- **Secondary / Ghost / Tertiary:**
  - **Secondary Court Button (`.secondary-court-btn`, `.top-util-btn`, `.history-dropdown-btn`):** Solid ivory `#faf7f2`, `1px solid #c2b8a6` border, `#1f1c18` text (`传讯官员`, `同步`, `展开奏报`, `往期`).
  - **Cinnabar Outline Button (`.outline-cinnabar-btn`):** Solid ivory `#faf7f2`, `1px solid #9e3a2e` border, `#9e3a2e` text (`审阅提案`).
  - **Disabled State (`:disabled`):** Solid muted stone `#e2dcd0` background, `#d2cabd` border, `#766d61` text at `opacity: 1` (`cursor: not-allowed`).
  - **Gear Icon Utility Button (`.top-gear-btn`):** Compact `30px × 30px` square button (`5px` radius) housing a 15px authored SVG gear icon that toggles `.top-gear-menu` (`调试真值视图`, `君主访问凭据`).

### Chips & Dropdowns
Compact controls represent historical week selection, state selectors, channel switches, and binary approval decisions.
- **Style:** `4px`–`6px` border radius, `1px solid #dcd4c6` border, `--font-sans-cn` typography (`12px`–`13.5px`).
- **State:**
  - **History Week Dropdown (`.history-dropdown-menu` > `.history-dropdown-item`):** Lists only available dated weeks (`1 .. current_active_week`), highlighting the selected date (`.is-selected`) with `color: #9e3a2e`, `font-weight: 700`, `background: #f9f3ee`.
  - **Approval Decision Radio Pills (`.radio-pill`):** Equal-width flex pills (`padding: 5px 10px`, `border-radius: 5px`, `background: #f2ece1`). Selecting `拟批准` (`.selected-approve`) applies `background: rgba(88, 120, 84, 0.10)`, `border-color: #587854`, `color: #587854`; selecting `拟驳回` (`.selected-reject`) applies `background: rgba(158, 58, 46, 0.08)`, `border-color: #9e3a2e`, `color: #9e3a2e`.
  - **Mobile State Selector Pills (`.state-pill-btn`) & Severity Dots (`.pill-dot`):** Displayed on `<=960px` with an `8px` circular severity dot (`#9e3a2e` urgent, `#b87328` mild, `#587854` stable, `#7a7067` unknown).

### Cards / Containers
Floating panels and internal cards organize memorials, outliner summaries, and proposal line items without nested box clutter.
- **Corner Style:** `9px` on floating outer panels (`.left-court-sheet`, `.court-date-turn-box`, `.right-court-outliner`), `6px` on internal proposal/debug cards and outliner rows.
- **Background:** Outer floating panels use `rgba(250, 247, 242, 0.96)` (`#faf7f2` solid on `<=960px`); internal containers (`.central-budget-card`, `.state-proposal-card`, `.chat-messages-stream`) use `#f2ece1` (`--surface-subtle`) with `#faf7f2` inner line items (`.proposal-line-item`, `.central-num-box`, `.chat-bubble`).
- **Shadow Strategy:** Ambient elevation (`0 4px 16px rgba(31, 28, 24, 0.06)` and `0 3px 12px rgba(31, 28, 24, 0.05)`) on outer floating panels only; internal cards are flat.
- **Border:** `1px solid #dcd4c6` on panels and cards; `1px solid #eae3d5` horizontal hairline dividers on `.sheet-kv-row` (`padding: 13px 0`) and `.outliner-state-row` (`padding: 9px 10px`). Selected outliner row (`.outliner-state-row.is-selected`) highlights with `background: #f9f3ee; border-color: #9e3a2e`.
- **Internal Padding:** Left sheet header `18px 20px 12px`, tab panel `14px 20px 18px`; date-turn box `12px 16px`; right outliner `14px 16px`; modal card `18px 20px`.

### Inputs / Fields
Form fields appear in the court chat composer and the credential authentication modals.
- **Style:** Chat textarea (`.chat-textarea`) uses `#faf7f2` background, `1px solid #c2b8a6` border, `6px` radius, `padding: 7px 10px`, `font-size: 14px`, `resize: none`. Modal password inputs (`.modal-text-input`) use `#ffffff` background, `1px solid #c2b8a6` border, `5px` radius, `padding: 8px 11px`, `font-size: 14px`.
- **Focus:** `outline: 2px solid #9e3a2e; outline-offset: 2px`, with `caret-color: #9e3a2e`.
- **Error / Disabled:** Validation and auth errors render in `.inline-error-banner` (`background: rgba(158, 58, 46, 0.08)`, `border: 1px solid #9e3a2e`, `color: #9e3a2e`, `padding: 6px 10px`, `border-radius: 5px`). Disabled chat textarea in history or completed-trial view displays a read-only placeholder and blocks input.

### Navigation
- **Top-Left Compact Resource Bar (`.court-top-bar`) & Top-Right Date/Turn Box (`.court-date-turn-box`):** Split corner-anchored HUD exposing continuous map terrain across the top center, pairing central treasury metrics and gear utilities on the left with calendar date, `往期` dropdown, and `截止征询` / `下一回合` / `返回当前` / `试玩结束` controls on the right.
- **Sheet 3-Tab Bar (`.drawer-tabs-bar`):** Equal-width 3-column grid (`grid-template-columns: repeat(3, 1fr)`, `padding: 0 18px`, `border-bottom: 1px solid #dcd4c6`). Tabs (`本州奏报`, `朝堂会话`, `提案批复`) use `--font-serif-cn`, `16px`, `color: #685f54`, and `border-bottom: 2.5px solid transparent`. Active tab (`.drawer-tab-btn.active`) sets `color: #9e3a2e`, `border-bottom-color: #9e3a2e`, `font-weight: 700`.
- **Chat 4-Channel Selector (`.channel-selector-grid`):** 4-column pill bar (`grid-template-columns: repeat(4, 1fr); gap: 6px`) for the four monarch-visible channels (`甲州单聊`, `乙州单聊`, `丙州单聊`, `朝议群聊`).
- **Lower-Right Map Layer & Camera Dock (`.map-bottom-right-controls`):** Segmented 3-layer pill group (`灾情`, `存粮`, `存银`, active pill highlighted with `background: #fdfaf7; border-color: #9e3a2e; color: #9e3a2e; font-weight: 700`) paired with `+`, `−`, and `复位视图` camera buttons (`height: 34px`).

### Cartographic Map Layer & 5-State Legend
- **Jiangshan Cartographic Canvas (`.strategy-map-svg`):** Combines base ocean rice-paper (`#e5decb`), georeferenced hillshade raster (`terrain_relief.webp`, `opacity: 0.72`), deduplicated reference province/coastline vectors, multiply-blended playable territory washes (`fill-opacity: 0.30`), diagonal `UNKNOWN` hatching (`#unknown-hatch-pattern`), ranked blue rivers and lakes, cased cinnabar selection outlines (`#8c2d22`), and scale-compensated Songti labels (`◎ 治所`, secondary town dots, state titles, and layer sub-captions).
- **5-State Legend (`.map-legend-card`):** Displays five `14px × 11px` swatches (`border-radius: 2px; border: 1px solid rgba(31, 28, 24, 0.25)`) that dynamically adapt their labels to the active layer (`灾情`: `水患`/`旱灾`/`平稳`/`未奏报`/`周边地域`; `存粮`: `存粮匮乏`/`存粮偏紧`/`存粮充裕`/`未奏报`/`周边地域`; `存银`: `存银匮乏`/`存银偏紧`/`存银充裕`/`未奏报`/`周边地域`), keeping `未奏报` (diagonal hatch) visually distinct from both `0` and `周边地域` (`#e6dfcf`).

## Do's and Don'ts

### Do:
- **Do** keep the interactive geographic map at 100vw × 100vh with low-opacity multiply washes (fill-opacity: 0.30, 0.36 selected, 0.38 hover) so terrain relief and hydrography remain legible underneath.
- **Do** render unreported states (UNKNOWN) with the diagonal hatch pattern (#unknown-hatch-pattern) and explicit '本周未奏报（未知）' text rather than substituting 0 or background fills.
- **Do** use --font-serif-cn for state titles, top bar treasury metrics, calendar date display, drawer tabs, report key-value rows (.sheet-kv-row), and outliner state rows (.outliner-state-row), paired with tabular-nums on all resource figures.
- **Do** reserve --accent-cinnabar (#9e3a2e) for active phase/Action CTAs (截止征询, 下一回合, 发旨), selected tabs/pills, selected state borders (#8c2d22), and urgent disaster/shortage statuses.
- **Do** use the solid muted disabled tokens (background #e2dcd0, border #d2cabd, text #766d61, opacity: 1) on disabled action and primary buttons instead of translucent washed-out fills.
- **Do** maintain single-line 3-column state summaries (white-space: nowrap) in .right-court-outliner across 1586px, 1440px, and 1280px desktop breakpoints without middle-dot (`·`) text separators.

### Don't:
- **Don't** introduce ornate EU4-style gilded frames, heraldic crests, hanging pennants, decorative province paintings, or dark slate/charcoal panels.
- **Don't** display server truth values on the map, top bar, or state sheet unless Debug Truth mode is explicitly authenticated and active.
- **Don't** allow map labels, sub-captions, or lower-right map controls to bleed through or clip behind the open state sheet on <=960px mobile viewports.
- **Don't** use CSS transform scaling on the map container; perform all zoom and pan updates through the SVG viewBox and labelScale so strokes and typography stay crisp.
- **Don't** invent custom metaphors, fictional dynasty names, or non-standard accounting terms in UI copy; use the standard ledger labels (账面, 可支配, 未知).
