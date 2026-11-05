# Third-Party Notices & Licensing

## Original Simu-Emperor Code (`src/`, `tests/`, original `web/` application logic)

Original Simu-Emperor backend, simulation engine, officer agent runtime, and application logic are Copyright (c) 2025 simu-emperor contributors and licensed under the **MIT License** (see [`LICENSE`](./LICENSE)).

---

## Cartographic Map Layer & Shaded Relief (`DeanChensj/jiangshan-map`)

The interactive geographic map layer in the web frontend incorporates and adapts cartographic projection, camera interaction, hydrography, modern provincial/coastline outlines, and georeferenced shaded-relief terrain from:

- **Upstream Repository**: [`DeanChensj/jiangshan-map`](https://github.com/DeanChensj/jiangshan-map) ("江山时序 · Jiangshan Historical Atlas")
- **Upstream Commits**: `a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e` (base terrain, hydrography, and modern provincial outlines) and `7c5cfe3b575806fbe3158a85109c166cd4d0574f` (pinned `s_ming_c` 1636–1643 late-Ming Two Capitals & Thirteen Provinces snapshot)
- **Upstream Copyright**: Copyright (c) Jiangshan Atlas Contributors (`DeanChensj/jiangshan-map`)
- **Upstream License**: **GNU General Public License v3.0 (GPL-3.0)** — full license text in [`LICENSE-GPL-3.0.txt`](./LICENSE-GPL-3.0.txt)

### Included / Adapted Upstream Files & Assets

1. `web/assets/jiangshan/terrain_relief.webp`
   - Direct verbatim copy of `assets/terrain_relief.webp` from `DeanChensj/jiangshan-map` at commit `a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e` (`1600×1076` WebP; not AI-generated).
   - Georeferenced monochrome topographic hillshade raster aligned to `MercatorProjector(1000, 700, { west: 66, east: 142, south: 14, north: 55 })` at `x = -80, y = -40, width = 1160, height = 780` (shifted by `(-MAP_VIEWBOX_ORIGIN_X, -MAP_VIEWBOX_ORIGIN_Y)` alongside projected vectors).
2. `web/jiangshan-geo-data.ts`
   - Adapted from `js/china_geo_data.js` (commit `a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e`) and `js/atlas_snapshots.js` (pinned commit `7c5cfe3b575806fbe3158a85109c166cd4d0574f`) in `DeanChensj/jiangshan-map` under **GNU GPL v3.0**, including the lossless VLQ delta-ring decoder (`dec`), modern provincial/coastline boundary rings (`PROVINCE_OUTLINES`), river/lake hydrography (`HYDRO_DATA`, rendered at modern reference year `1990`), and the 15 late-Ming provincial units from the `s_ming_c` (`1636–1643`) snapshot (`1113, 1077..1090`) with their internal `s_ming_a` prefecture anchors.
3. `web/map-data.ts` & `web/components/MapViewport.tsx`
   - Incorporates `MercatorProjector` (`toScreen`, `toGeo`, `ringToSvgPath`, `smoothRingToSvgPath`), deduplicated interior/outer boundary path construction, SVG `viewBox` camera math, multi-pointer 2-finger pinch zoom, pointer-centered wheel zoom, captured pointer drag, and scale-aware label density adapted from `js/app.js` and `css/style.css` in `DeanChensj/jiangshan-map` (`a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e` and `7c5cfe3b575806fbe3158a85109c166cd4d0574f`).
   - Renders the 15 late-Ming provincial units (`beizhili`, `nanzhili`, `shandong`, `shanxi`, `henan`, `shaanxi`, `sichuan`, `huguang`, `zhejiang`, `jiangxi`, `fujian`, `guangdong`, `guangxi`, `yunnan`, `guizhou`) on the `s_ming_c` (`1636–1643`) layer with explicit resolution between Jiangshan provider region IDs (`1113, 1077..1090`) and game `ProvinceId` values (`shaanxi`, `henan`, `huguang` active; other 12 frozen and clickable).

### Combined Frontend Distribution License

Because the web frontend (`web/` and built `out/`) links and distributes GPL-3.0 cartographic code, vector outlines, hydrography, and terrain assets from `DeanChensj/jiangshan-map`, the combined/derived frontend distribution is made available under the terms of the **GNU General Public License v3.0 (GPL-3.0)** (see [`LICENSE-GPL-3.0.txt`](./LICENSE-GPL-3.0.txt)), while original standalone Simu-Emperor backend/engine code remains dual-usable under the original MIT License.

The shaded-relief WebP retains the upstream file unchanged; its source provenance is recorded in `web/assets/jiangshan/terrain_relief.webp.json`.

---

## Kumo UI Components (`cloudflare/kumo` via Periplus Reference Extract)

Selected controlled UI primitives under `components/kumo/` (`button`, `dialog`, `field`, `input`, `label`, `layer-card`, `loader`, `tooltip`, plus `utils/` and `styles/`) are adapted from:

- **Upstream Repository**: [`cloudflare/kumo`](https://github.com/cloudflare/kumo)
- **Upstream Commit**: `fedc8a771d499ccceb309ec45b2b11d74eea3963` (via Periplus reference extract `8f7a3c1`)
- **Upstream Copyright**: Copyright (c) 2025 Cloudflare, Inc.
- **Upstream License**: **MIT License** — full license text in [`components/kumo/LICENSE`](./components/kumo/LICENSE) and provenance metadata in [`components/kumo/source.json`](./components/kumo/source.json)

---

## Noto Sans SC UI Subset Font (`public/assets/NotoSansSC-ui.woff2`)

The bundled Chinese UI sans-serif webfont subset (`public/assets/NotoSansSC-ui.woff2`) is derived from **Noto Sans SC**:

- **Copyright**: Copyright 2014-2021 Adobe (`http://www.adobe.com/`), with Reserved Font Name 'Source'
- **License**: **SIL Open Font License, Version 1.1 (OFL-1.1)** — full license text in [`public/assets/OFL-NotoSansSC.txt`](./assets/OFL-NotoSansSC.txt)

---

## Original Ming Strategy HUD Art Assets (`public/assets/eu-hud/`)

The HUD frame, textures, badge, button chrome, painted icon sprite sheet, and character portrait sheet under `public/assets/eu-hud/` (`ornate-frame.png`, `portraits.png`, `function-icons.png`, `imperial-badge.svg`, `brass-button.svg`, `enamel.svg`, `parchment.svg`) are original project-created assets (see [`public/assets/eu-hud/README.md`](./assets/eu-hud/README.md)) and contain no third-party game files or screenshots.
