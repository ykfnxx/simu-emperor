# Third-Party Notices & Licensing

## Original Simu-Emperor Code (`src/`, `tests/`, original `web/` application logic)

Original Simu-Emperor backend, simulation engine, officer agent runtime, and application logic are Copyright (c) 2025 simu-emperor contributors and licensed under the **MIT License** (see [`LICENSE`](./LICENSE)).

---

## Cartographic Map Layer & Shaded Relief (`DeanChensj/jiangshan-map`)

The interactive geographic map layer in the web frontend incorporates and adapts cartographic projection, camera interaction, hydrography, modern provincial/coastline outlines, and georeferenced shaded-relief terrain from:

- **Upstream Repository**: [`DeanChensj/jiangshan-map`](https://github.com/DeanChensj/jiangshan-map) ("江山时序 · Jiangshan Historical Atlas")
- **Upstream Commit**: `a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e`
- **Upstream Copyright**: Copyright (c) Jiangshan Atlas Contributors (`DeanChensj/jiangshan-map`)
- **Upstream License**: **GNU General Public License v3.0 (GPL-3.0)** — full license text in [`LICENSE-GPL-3.0.txt`](./LICENSE-GPL-3.0.txt)

### Included / Adapted Upstream Files & Assets

1. `web/assets/jiangshan/terrain_relief.webp`
   - Direct verbatim copy of `assets/terrain_relief.webp` from `DeanChensj/jiangshan-map` at commit `a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e` (`1600×1076` WebP; not AI-generated).
   - Georeferenced monochrome topographic hillshade raster aligned to `MercatorProjector(1000, 700, { west: 66, east: 142, south: 14, north: 55 })` at `x = -80, y = -40, width = 1160, height = 780` (shifted by `(-MAP_VIEWBOX_ORIGIN_X, -MAP_VIEWBOX_ORIGIN_Y)` alongside projected vectors).
2. `web/jiangshan-geo-data.ts`
   - Adapted from `js/china_geo_data.js` in `DeanChensj/jiangshan-map` at commit `a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e` under **GNU GPL v3.0**, including the lossless VLQ delta-ring decoder (`dec`), modern provincial/coastline boundary rings (`PROVINCE_OUTLINES`), and river/lake hydrography (`HYDRO_DATA`, rendered at modern reference year `1990`).
   - Academic-only historical dynasty/CHGIS/Hartwell snapshot datasets (`atlas_snapshots.js`, `map_data.js`, `lore_data.js`) are **not** included.
3. `web/map-data.ts` & `web/components/MapViewport.tsx`
   - Incorporates `MercatorProjector` (`toScreen`, `toGeo`, `ringToSvgPath`, `smoothRingToSvgPath`), deduplicated interior/outer boundary path construction, SVG `viewBox` camera math, multi-pointer 2-finger pinch zoom, pointer-centered wheel zoom, captured pointer drag, and scale-aware label density adapted from `js/app.js` and `css/style.css` in `DeanChensj/jiangshan-map` (`a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e`).
   - Playable state territories (`甲州`, `乙州`, `丙州`) are constructed by merging modern provincial boundary rings from `JIANGSHAN_PROVINCE_OUTLINES` (`山西省+河南省`, `安徽省+江苏省+上海市+浙江省`, `湖北省+湖南省+江西省`) into fictional game jurisdictions in the shared `MercatorProjector` coordinate space (not original hand-drawn coordinates and not historical CHGIS dynasty boundaries).

### Combined Frontend Distribution License

Because the web frontend (`web/` and built `dist/web/`) links and distributes GPL-3.0 cartographic code, vector outlines, hydrography, and terrain assets from `DeanChensj/jiangshan-map`, the combined/derived frontend distribution is made available under the terms of the **GNU General Public License v3.0 (GPL-3.0)** (see [`LICENSE-GPL-3.0.txt`](./LICENSE-GPL-3.0.txt)), while original standalone Simu-Emperor backend/engine code remains dual-usable under the original MIT License.

The shaded-relief WebP retains the upstream file unchanged; its source provenance is recorded in `web/assets/jiangshan/terrain_relief.webp.json`.
