---
surface: web/App.tsx
mode: operate
world: simple-cartographic-interface
direction_source: DeanChensj/jiangshan-map (a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e) cartographic layer + EU4 spatial layout only
---

# Surface Brief: `web/App.tsx` (Operate — Simple Cartographic Interface + `jiangshan-map` Layer)

## 1. Visual World & Cartographic Layer (`DeanChensj/jiangshan-map`)
- **Primary Canvas**: Full-viewport (`100vw × 100vh`) geographic map directly incorporating `MercatorProjector`, `terrain_relief.webp` (`web/assets/jiangshan/terrain_relief.webp` at `opacity: 0.72`), deduplicated interior/outer regional boundary construction (`getBackgroundGeographyLayer`), ranked rivers/lakes (`getProjectedHydroLayer`), and 2D occlusion-aware SVG `viewBox` camera math (`computeSvgCameraViewBox`, `zoomCameraAtClientPoint`, `computeMinimalOcclusionPan`) adapted from `DeanChensj/jiangshan-map` (`a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e`, GPL-3.0; see `THIRD_PARTY_NOTICES.md`).
- **Playable Territories**: Three neutral fictional territories (`甲州` north-central, `乙州` center-east, `丙州` southwest) constructed from merged reference provincial rings and rendered with low-opacity watercolor washes (`mix-blend-mode: multiply; fill-opacity: 0.30`, `0.36` selected, `0.38` hover) over the shaded relief so topographic mountains, rivers (`清河`, `沧澜水`), and lakes remain clearly visible.
- **UI Panels & Typography**: Warm ivory floating panels (`rgba(250, 247, 242, 0.96)`, solid `#FAF7F2` on `<=960px` mobile) with `1px solid #DCD4C6` hairlines and `1px solid #EAE3D5` row dividers. Classical Chinese Songti (`--font-serif-cn`) carries state titles, top treasury figures, sheet tabs, report key-value labels/values, outliner rows, and map labels; clean sans-serif (`--font-sans-cn`) handles operational buttons, timeline pills, chat streams, and inputs. Zero ornate frames, crests, pennants, province paintings, or dark chrome.
- **Semantic Palette (Report-Only)**:
  - Urgent (`urgent`): Cinnabar (`#9E3A2E` UI accent, `#B54434` map wash, `#8C2D22` selected border)
  - Mild (`mild`): Ochre (`#B87328` UI accent, `#C88A3B` map wash)
  - Stable (`stable`): Sage (`#587854` UI accent, `#7A9A76` map wash)
  - Unknown (`unknown`): Slate (`#7A7067` UI dot/border, `#9A9488` wash + `url(#unknown-hatch-pattern)` 45-degree diagonal hatch, `本周未奏报（未知）`), strictly distinct from `0` and from `background` (`周边地域`).

## 2. Spatial Architecture (EU4 Layout Only)
- **Unified Top HUD Bar (`.court-top-bar`, `52px` default / `50px` at `<=1460px` / `min-height: 48px` at `<=1320px`)**:
  - Left: `朝廷存银 X.X万两` | `朝廷存粮 X.X万石` + `来源：第N周度支奏报` pill (or `本周未奏报（未知）` when `UNKNOWN`), plus `[真值 ...]` pill when Debug Truth is active.
  - Center (flanked by two `1px × 20px` vertical stone dividers on desktop): 4 connected week timeline pills (`第1周·已归档` › `第2周·征询中` › `第3周` › `第4周`) + `返回第N周` when viewing history, or `四周已完结` badge on completion.
  - Right: `[同步]`, `[截止征询]`, `[批复结算]`, conditional `[展开奏报]`, and soft-underlined `调试` / `凭证` links.
- **Left Closable State Sheet (`.left-court-sheet`, `404px` wide at `top: 76px, left: 18px` default; `386px` at `<=1460px`; `360px` at `<=1320px`)**:
  - Report tab (`.is-tab-report`) maintains `min-height: min(702px, calc(100vh - 96px))` (`684px` at `<=1460px`, `636px` at `<=1320px`).
  - Header with 27px Songti state title (`乙州`), subtitle (`第N周官员奏报 · 洪灾`), compact state pills (`甲`/`乙`/`丙`, shown on `<=960px` mobile), and `✕` close button.
  - 3 equal-width Songti text tabs (`本州奏报` | `朝堂会话` | `提案批复`) with `2.5px` cinnabar active underline.
  - `本州奏报` presents 5 hairline-separated Songti key-value rows (`灾情状态`, `可支配存粮` + `已扣本周支出` sub-note with full ledger formula in `title`, `可支配存银`, `本州赈灾需求`, `向朝廷请拨`), `奏折摘要` + `来源：第N周`, optional Debug Truth diff card, and 2 side-by-side footer buttons (`传讯{X}州官员`, `审阅{X}州提案`).
- **Right Concise Outliner (`.right-court-outliner`, `324px` wide at `top: 76px, right: 18px` default; `312px` at `<=1460px`; `296px` at `<=1320px`)**:
  - `各州奏报（第N周）` Songti header + 3 single-line Songti state status rows (`甲州`, `乙州`, `丙州` with severity dot and `white-space: nowrap` summary such as `旱灾 · 请粮1.0万石/请银1.5万两`).
- **Lower-Right Map Controls & 5-State Legend (`.map-bottom-right-controls`, `right: 18px, bottom: 18px`)**:
  - Layer switcher (`灾情` | `存粮` | `存银`) + camera buttons (`+`, `−`, `复位视图`) + 5-state legend (`水患`/`旱灾`/`平稳`/`未奏报`/`周边地域`, dynamically relabeled for `存粮` and `存银` layers).
- **Mobile Reflow (`<=960px`, validated at `390×844`)**:
  - Stacked flex column (`padding: 6px; gap: 6px`): top HUD bar wraps into a relative card, `.right-court-outliner` hides (`display: none`), header `甲`/`乙`/`丙` pills enable state switching, `.left-court-sheet` fills remaining height (`flex: 1; width: 100%; background: #FAF7F2`), `.chat-messages-stream` expands with `max-height: none; flex: 1`, and `.map-viewport.is-drawer-open` hides `.map-camera-stage` and `.map-bottom-right-controls` while the sheet is open; closing the sheet reveals the full pinch/drag map and `[展开奏报]` button.
