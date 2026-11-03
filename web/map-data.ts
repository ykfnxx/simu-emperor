/**
 * Cartographic Projection, Georeferenced Layers & Camera Math
 *
 * Incorporates `MercatorProjector`, deduplicated boundary path construction,
 * hydrography projection, and SVG `viewBox` camera math adapted from
 * `js/app.js` in `DeanChensj/jiangshan-map` (commit a9cd67c3c4c5eef5902d31104df9b5a7ec83aa0e)
 * under GNU GPL v3.0. See `THIRD_PARTY_NOTICES.md` and `LICENSE-GPL-3.0.txt`.
 */

import {
  BACKGROUND_REGIONS,
  formatWan,
  PLAYABLE_STATES,
  type CourtStateView,
  type MapReportSeverity,
  type StateId,
} from '../src/contracts/index.ts';
import {
  JIANGSHAN_HYDRO_DATA,
  JIANGSHAN_PROVINCE_OUTLINES,
  type GeoCoord,
} from './jiangshan-geo-data.ts';

const RAD_TO_DEG = 180 / Math.PI;
const DEG_TO_RAD = Math.PI / 180;

export type MapLayerKind = 'disaster' | 'grain' | 'silver';

export interface MapCameraState {
  panX: number;
  panY: number;
  zoom: number;
}

export const MAP_VIEWBOX_ORIGIN_X = 395;
export const MAP_VIEWBOX_ORIGIN_Y = 278;
export const MAP_VIEWBOX_WIDTH = 460;
export const MAP_VIEWBOX_HEIGHT = 288;

export const LEFT_SHEET_OCCLUSION_RATIO = 0.34;
export const LEFT_SHEET_SAFE_TARGET_RATIO = 0.44;
export const RIGHT_OUTLINER_OCCLUSION_RATIO = 0.75;
export const RIGHT_OUTLINER_SAFE_TARGET_RATIO = 0.66;
export const TOP_HUD_OCCLUSION_RATIO = 0.18;
export const TOP_HUD_SAFE_TARGET_RATIO = 0.28;
export const BOTTOM_CONTROLS_OCCLUSION_RATIO = 0.78;
export const BOTTOM_CONTROLS_SAFE_TARGET_RATIO = 0.68;

export const INITIAL_MAP_CAMERA: MapCameraState = {
  panX: 0,
  panY: 0,
  zoom: 1,
};

export interface MapBounds {
  west: number;
  east: number;
  south: number;
  north: number;
}

/**
 * Spherical Mercator projector ported verbatim from `DeanChensj/jiangshan-map` (`js/app.js` lines 26–54),
 * with an additive viewBox origin shift `(-MAP_VIEWBOX_ORIGIN_X, -MAP_VIEWBOX_ORIGIN_Y)` so vector
 * outlines, hydrography, and `terrain_relief.webp` share 0.0-drift georeferenced registration.
 */
export class MercatorProjector {
  readonly width: number;
  readonly height: number;
  readonly bounds: MapBounds;
  readonly scale: number;
  readonly padX: number;
  readonly padY: number;
  readonly northMerc: number;
  readonly offsetX: number;
  readonly offsetY: number;

  constructor(
    width = 1000,
    height = 700,
    bounds: MapBounds = { west: 66, east: 142, south: 14, north: 55 },
    offsetX = -MAP_VIEWBOX_ORIGIN_X,
    offsetY = -MAP_VIEWBOX_ORIGIN_Y,
  ) {
    this.width = width;
    this.height = height;
    this.bounds = bounds;
    this.offsetX = offsetX;
    this.offsetY = offsetY;

    const spanLng = bounds.east - bounds.west;
    const spanLat = (this._latToMerc(bounds.north) - this._latToMerc(bounds.south)) * RAD_TO_DEG;
    this.scale = Math.min(width / spanLng, height / spanLat);
    this.padX = (width - spanLng * this.scale) * 0.5;
    this.padY = (height - spanLat * this.scale) * 0.5;
    this.northMerc = this._latToMerc(bounds.north);
  }

  _latToMerc(lat: number): number {
    return Math.log(Math.tan(Math.PI * 0.25 + (lat * DEG_TO_RAD) * 0.5));
  }

  toScreen(lng: number, lat: number): [number, number] {
    const x = (lng - this.bounds.west) * this.scale + this.padX + this.offsetX;
    const y =
      (this.northMerc - this._latToMerc(lat)) * RAD_TO_DEG * this.scale +
      this.padY +
      this.offsetY;
    return [x, y];
  }

  toGeo(x: number, y: number): [number, number] {
    const rawX = x - this.offsetX;
    const rawY = y - this.offsetY;
    const lng = (rawX - this.padX) / this.scale + this.bounds.west;
    const merc = this.northMerc - (rawY - this.padY) / (this.scale * RAD_TO_DEG);
    const lat = (2 * Math.atan(Math.exp(merc)) - Math.PI * 0.5) * RAD_TO_DEG;
    return [lng, lat];
  }

  ringToSvgPath(ring: GeoCoord[]): string {
    if (!ring || ring.length < 2) {
      return '';
    }
    let out = '';
    for (let i = 0; i < ring.length; i++) {
      const pt = ring[i]!;
      const [x, y] = this.toScreen(pt[0], pt[1]);
      out += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    return out + 'Z';
  }

  smoothRingToSvgPath(ring: GeoCoord[]): string {
    if (!ring || ring.length < 3) {
      return this.ringToSvgPath(ring);
    }
    const pts: Array<[number, number]> = [];
    for (let i = 0; i < ring.length; i++) {
      const r = ring[i]!;
      const p = this.toScreen(r[0], r[1]);
      if (
        !pts.length ||
        Math.hypot(p[0] - pts[pts.length - 1]![0], p[1] - pts[pts.length - 1]![1]) > 0.6
      ) {
        pts.push(p);
      }
    }
    if (
      pts.length > 1 &&
      Math.hypot(pts[0]![0] - pts[pts.length - 1]![0], pts[0]![1] - pts[pts.length - 1]![1]) < 1.0
    ) {
      pts.pop();
    }
    const n = pts.length;
    if (n < 3) {
      return this.ringToSvgPath(ring);
    }

    const sx = new Float64Array(n);
    const sy = new Float64Array(n);
    const ex = new Float64Array(n);
    const ey = new Float64Array(n);
    const curved = new Uint8Array(n);

    for (let i = 0; i < n; i++) {
      const p0 = pts[i]!;
      const p1 = pts[(i + 1) % n]!;
      const dx = p1[0] - p0[0];
      const dy = p1[1] - p0[1];
      const len = Math.hypot(dx, dy);
      if (len >= 1.6) {
        const t = Math.min(0.28, 4.2 / len);
        sx[i] = p0[0] + dx * t;
        sy[i] = p0[1] + dy * t;
        ex[i] = p1[0] - dx * t;
        ey[i] = p1[1] - dy * t;
        curved[i] = 1;
      } else {
        sx[i] = p0[0];
        sy[i] = p0[1];
        ex[i] = p1[0];
        ey[i] = p1[1];
      }
    }

    let out = `M${sx[0]!.toFixed(1)} ${sy[0]!.toFixed(1)}`;
    for (let i = 0; i < n; i++) {
      const next = (i + 1) % n;
      if (curved[i]) {
        out += `L${ex[i]!.toFixed(1)} ${ey[i]!.toFixed(1)}`;
      }
      const vx = pts[next]![0];
      const vy = pts[next]![1];
      if (curved[i] && curved[next]) {
        out += `Q${vx.toFixed(1)} ${vy.toFixed(1)} ${sx[next]!.toFixed(1)} ${sy[next]!.toFixed(1)}`;
      } else {
        out += `L${sx[next]!.toFixed(1)} ${sy[next]!.toFixed(1)}`;
      }
    }
    return out + 'Z';
  }

  _orientRing(ring: GeoCoord[], isHole = false): GeoCoord[] {
    if (!ring || ring.length < 3) {
      return ring;
    }
    let area2 = 0;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      area2 += ring[j]![0] * ring[i]![1] - ring[i]![0] * ring[j]![1];
    }
    if (area2 === 0) {
      return ring;
    }
    const wantPositive = !isHole;
    if (area2 > 0 !== wantPositive) {
      return ring.slice().reverse();
    }
    return ring;
  }

  multiRingsToSvgPath(polygons: GeoCoord[][][]): string {
    return polygons
      .map((poly) =>
        poly.map((r, idx) => this.ringToSvgPath(this._orientRing(r, idx > 0))).join(''),
      )
      .join('');
  }

  static pointInRing(lng: number, lat: number, ring: GeoCoord[]): boolean {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i]!;
      const [xj, yj] = ring[j]!;
      if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-12) + xi) {
        inside = !inside;
      }
    }
    return inside;
  }
}

export const PROJECTOR = new MercatorProjector();

/**
 * Georeferenced placement of `terrain_relief.webp` (`x=-80, y=-40, w=1160, h=780` in raw 1000x700 space).
 */
export const TERRAIN_RELIEF_RECT = {
  x: -80 - MAP_VIEWBOX_ORIGIN_X,
  y: -40 - MAP_VIEWBOX_ORIGIN_Y,
  width: 1160,
  height: 780,
} as const;

export interface TownPoint {
  name: string;
  x: number;
  y: number;
}

export interface PlayableProvinceGeometry {
  state_id: StateId;
  state_name: string;
  is_playable: true;
  d: string;
  subBoundaryPath: string;
  center: { x: number; y: number };
  seat: { name: string; x: number; y: number };
  towns: TownPoint[];
}

export interface BackgroundRegionGeometry {
  province_id: string;
  region_name: string;
  display_caption: string;
  is_playable: false;
  map_status_label: '地理背景区（未启用）';
  labelPos: { x: number; y: number };
}

function ptKey(pt: GeoCoord): string {
  return `${Math.round(pt[0] * 100)},${Math.round(pt[1] * 100)}`;
}

function edgeKey(p1: GeoCoord, p2: GeoCoord): string {
  const k1 = ptKey(p1);
  const k2 = ptKey(p2);
  return k1 < k2 ? `${k1}|${k2}` : `${k2}|${k1}`;
}

function buildMergedTerritoryGeometry(titles: string[]): {
  outerRing: GeoCoord[];
  subBoundaryPath: string;
} {
  const titleSet = new Set(titles);
  const edgeCounts = new Map<string, number>();
  const directedEdges: Array<{
    p1: GeoCoord;
    p2: GeoCoord;
    k1: string;
    k2: string;
    ek: string;
  }> = [];

  for (const prov of JIANGSHAN_PROVINCE_OUTLINES) {
    if (!titleSet.has(prov.title)) {
      continue;
    }
    const ring = prov.rings[0]?.[0];
    if (!ring || ring.length < 3) {
      continue;
    }
    for (let i = 0; i < ring.length - 1; i++) {
      const p1 = ring[i]!;
      const p2 = ring[i + 1]!;
      if (ptKey(p1) === ptKey(p2)) {
        continue;
      }
      const ek = edgeKey(p1, p2);
      edgeCounts.set(ek, (edgeCounts.get(ek) ?? 0) + 1);
      directedEdges.push({ p1, p2, k1: ptKey(p1), k2: ptKey(p2), ek });
    }
  }

  const outerEdges = directedEdges.filter((e) => edgeCounts.get(e.ek) === 1);
  const nextMap = new Map<string, typeof outerEdges>();
  for (const e of outerEdges) {
    const list = nextMap.get(e.k1);
    if (list) {
      list.push(e);
    } else {
      nextMap.set(e.k1, [e]);
    }
  }

  const used = new Set<(typeof outerEdges)[number]>();
  const loops: GeoCoord[][] = [];
  for (const e of outerEdges) {
    if (used.has(e)) {
      continue;
    }
    const loop: GeoCoord[] = [e.p1];
    let cur = e;
    used.add(cur);
    while (true) {
      loop.push(cur.p2);
      const candidates = (nextMap.get(cur.k2) ?? []).filter((n) => !used.has(n));
      if (!candidates.length) {
        break;
      }
      cur = candidates[0]!;
      used.add(cur);
    }
    loops.push(loop);
  }
  loops.sort((a, b) => b.length - a.length);
  const outerRing = loops[0] ?? [];

  const seenSub = new Set<string>();
  let subBoundaryPath = '';
  let penX = NaN;
  let penY = NaN;
  for (const e of directedEdges) {
    if ((edgeCounts.get(e.ek) ?? 0) < 2 || seenSub.has(e.ek)) {
      penX = NaN;
      penY = NaN;
      continue;
    }
    seenSub.add(e.ek);
    const [x1, y1] = PROJECTOR.toScreen(e.p1[0], e.p1[1]);
    const [x2, y2] = PROJECTOR.toScreen(e.p2[0], e.p2[1]);
    if (Math.hypot(x2 - x1, y2 - y1) < 0.05) {
      continue;
    }
    if (x1 !== penX || y1 !== penY) {
      subBoundaryPath += `M${x1.toFixed(1)} ${y1.toFixed(1)}`;
    }
    subBoundaryPath += `L${x2.toFixed(1)} ${y2.toFixed(1)}`;
    penX = x2;
    penY = y2;
  }

  return { outerRing, subBoundaryPath };
}

function projectPt(lng: number, lat: number): { x: number; y: number } {
  const [x, y] = PROJECTOR.toScreen(lng, lat);
  return {
    x: Number(x.toFixed(1)),
    y: Number(y.toFixed(1)),
  };
}

const stateAGeom = buildMergedTerritoryGeometry(['山西省', '河南省']);
const stateBGeom = buildMergedTerritoryGeometry(['安徽省', '江苏省', '上海市', '浙江省']);
const stateCGeom = buildMergedTerritoryGeometry(['湖北省', '湖南省', '江西省']);

export const PLAYABLE_PROVINCE_GEOMETRIES: readonly PlayableProvinceGeometry[] = [
  {
    state_id: 'state_a',
    state_name: PLAYABLE_STATES.state_a.state_name,
    is_playable: true,
    d: PROJECTOR.smoothRingToSvgPath(stateAGeom.outerRing),
    subBoundaryPath: stateAGeom.subBoundaryPath,
    center: projectPt(113.1, 36.35),
    seat: { name: '甲州治所', ...projectPt(112.9, 34.85) },
    towns: [
      { name: '临安', ...projectPt(112.7, 37.9) },
      { name: '镇西', ...projectPt(110.6, 35.1) },
      { name: '安平', ...projectPt(114.9, 34.4) },
    ],
  },
  {
    state_id: 'state_b',
    state_name: PLAYABLE_STATES.state_b.state_name,
    is_playable: true,
    d: PROJECTOR.smoothRingToSvgPath(stateBGeom.outerRing),
    subBoundaryPath: stateBGeom.subBoundaryPath,
    center: projectPt(118.1, 32.35),
    seat: { name: '乙州治所', ...projectPt(118.5, 30.75) },
    towns: [
      { name: '怀德', ...projectPt(116.5, 33.85) },
      { name: '永宁', ...projectPt(119.8, 33.2) },
      { name: '新昌', ...projectPt(117.2, 29.85) },
      { name: '广平', ...projectPt(119.9, 29.5) },
    ],
  },
  {
    state_id: 'state_c',
    state_name: PLAYABLE_STATES.state_c.state_name,
    is_playable: true,
    d: PROJECTOR.smoothRingToSvgPath(stateCGeom.outerRing),
    subBoundaryPath: stateCGeom.subBoundaryPath,
    center: projectPt(112.8, 28.95),
    seat: { name: '丙州治所', ...projectPt(112.6, 27.55) },
    towns: [
      { name: '大宁', ...projectPt(110.9, 30.8) },
      { name: '平乐', ...projectPt(109.5, 28.0) },
      { name: '武阳', ...projectPt(110.8, 26.7) },
      { name: '长林', ...projectPt(114.9, 26.5) },
    ],
  },
] as const;

export const BACKGROUND_REGION_GEOMETRIES: readonly BackgroundRegionGeometry[] = [
  {
    ...BACKGROUND_REGIONS[0]!,
    display_caption: '北境山地',
    labelPos: projectPt(109.8, 39.3),
  },
  {
    ...BACKGROUND_REGIONS[1]!,
    display_caption: '西川谷地',
    labelPos: projectPt(107.6, 31.6),
  },
  {
    ...BACKGROUND_REGIONS[2]!,
    display_caption: '东海湾',
    labelPos: projectPt(124.8, 29.5),
  },
] as const;

export interface WaterCaption {
  id: string;
  name: string;
  x: number;
  y: number;
  rot: number;
}

export const WATER_CAPTIONS: readonly WaterCaption[] = [
  {
    id: 'canglan-east',
    name: '沧澜水',
    ...projectPt(116.0, 30.95),
    rot: -18,
  },
  {
    id: 'qinghe-north',
    name: '清河',
    ...projectPt(116.0, 35.1),
    rot: -14,
  },
] as const;

export interface BackgroundGeographyLayer {
  landmassShapes: string[];
  interiorBoundaries: string;
  outerBoundaries: string;
  combinedBoundaries: string;
}

let cachedBackgroundGeography: BackgroundGeographyLayer | null = null;

/**
 * Builds the neutral surrounding landmass shapes and deduplicated interior/outer
 * boundary paths from `JIANGSHAN_PROVINCE_OUTLINES`, directly following
 * `_buildModernProvinces` and `_buildProvinceBoundaryPaths` in `jiangshan-map/js/app.js`.
 */
export function getBackgroundGeographyLayer(): BackgroundGeographyLayer {
  if (cachedBackgroundGeography) {
    return cachedBackgroundGeography;
  }
  const numPtKey = (pt: GeoCoord) => Math.round(pt[0] * 100) * 10000 + Math.round(pt[1] * 100);
  const numEdgeKey = (p1: GeoCoord, p2: GeoCoord) => {
    const k1 = numPtKey(p1);
    const k2 = numPtKey(p2);
    return k1 < k2 ? `${k1}|${k2}` : `${k2}|${k1}`;
  };

  const landmassShapes: string[] = [];
  const allRings: GeoCoord[][] = [];
  const edgeCounts = new Map<string, number>();

  for (const prov of JIANGSHAN_PROVINCE_OUTLINES) {
    if (!prov || String(prov.code).includes('_JD') || !Array.isArray(prov.rings)) {
      continue;
    }
    const d = PROJECTOR.multiRingsToSvgPath(prov.rings);
    if (d) {
      landmassShapes.push(d);
    }
    for (const poly of prov.rings) {
      for (const ring of poly ?? []) {
        if (!ring || ring.length < 2) {
          continue;
        }
        allRings.push(ring);
        for (let i = 0; i < ring.length - 1; i++) {
          const ek = numEdgeKey(ring[i]!, ring[i + 1]!);
          edgeCounts.set(ek, (edgeCounts.get(ek) ?? 0) + 1);
        }
      }
    }
  }

  const seenInterior = new Set<string>();
  const seenOuter = new Set<string>();
  let interiorBoundaries = '';
  let outerBoundaries = '';

  for (const ring of allRings) {
    let intPenX = NaN;
    let intPenY = NaN;
    let outPenX = NaN;
    let outPenY = NaN;
    for (let i = 0; i < ring.length - 1; i++) {
      const p1 = ring[i]!;
      const p2 = ring[i + 1]!;
      const ek = numEdgeKey(p1, p2);
      const count = edgeCounts.get(ek) ?? 0;
      if (count >= 2) {
        outPenX = NaN;
        outPenY = NaN;
        if (seenInterior.has(ek)) {
          intPenX = NaN;
          intPenY = NaN;
          continue;
        }
        seenInterior.add(ek);
        const [x1, y1] = PROJECTOR.toScreen(p1[0], p1[1]);
        const [x2, y2] = PROJECTOR.toScreen(p2[0], p2[1]);
        if (Math.hypot(x2 - x1, y2 - y1) < 0.05) {
          continue;
        }
        if (x1 !== intPenX || y1 !== intPenY) {
          interiorBoundaries += `M${x1.toFixed(1)} ${y1.toFixed(1)}`;
        }
        interiorBoundaries += `L${x2.toFixed(1)} ${y2.toFixed(1)}`;
        intPenX = x2;
        intPenY = y2;
      } else {
        intPenX = NaN;
        intPenY = NaN;
        if (seenOuter.has(ek)) {
          outPenX = NaN;
          outPenY = NaN;
          continue;
        }
        seenOuter.add(ek);
        const [x1, y1] = PROJECTOR.toScreen(p1[0], p1[1]);
        const [x2, y2] = PROJECTOR.toScreen(p2[0], p2[1]);
        if (Math.hypot(x2 - x1, y2 - y1) < 0.05) {
          continue;
        }
        if (x1 !== outPenX || y1 !== outPenY) {
          outerBoundaries += `M${x1.toFixed(1)} ${y1.toFixed(1)}`;
        }
        outerBoundaries += `L${x2.toFixed(1)} ${y2.toFixed(1)}`;
        outPenX = x2;
        outPenY = y2;
      }
    }
  }

  cachedBackgroundGeography = {
    landmassShapes,
    interiorBoundaries,
    outerBoundaries,
    combinedBoundaries: `${interiorBoundaries}${outerBoundaries}`,
  };
  return cachedBackgroundGeography;
}

export interface ProjectedHydroLayer {
  lakes: Array<{ d: string; major: boolean }>;
  trunkCasingPaths: string[];
  rivers: Array<{ d: string; rankClass: 'rank-trunk' | 'rank-major' | 'rank-med' | 'rank-minor' }>;
}

let cachedHydroLayer: ProjectedHydroLayer | null = null;

/**
 * Projects lakes and ranked rivers from `JIANGSHAN_HYDRO_DATA`, directly adapted from
 * `_buildTerrainRivers` in `jiangshan-map/js/app.js`.
 */
export function getProjectedHydroLayer(): ProjectedHydroLayer {
  if (cachedHydroLayer) {
    return cachedHydroLayer;
  }
  const refYear = 1990;
  const isVisible = (item: { appear?: number; vanish?: number }) => {
    if (item.appear !== undefined && refYear < item.appear) {
      return false;
    }
    if (item.vanish !== undefined && refYear >= item.vanish) {
      return false;
    }
    return true;
  };

  const lakes: Array<{ d: string; major: boolean }> = [];
  for (const lk of JIANGSHAN_HYDRO_DATA.lakes) {
    if (!isVisible(lk)) {
      continue;
    }
    const d = (lk.rings ?? []).map((r) => PROJECTOR.ringToSvgPath(r)).join('');
    if (!d) {
      continue;
    }
    lakes.push({ d, major: lk.rank <= 2 });
  }

  const trunkCasingPaths: string[] = [];
  const rivers: ProjectedHydroLayer['rivers'] = [];
  for (const riv of JIANGSHAN_HYDRO_DATA.rivers) {
    if (!isVisible(riv)) {
      continue;
    }
    let d = '';
    for (const line of riv.lines ?? []) {
      for (let i = 0; i < line.length; i++) {
        const pt = line[i]!;
        const [px, py] = PROJECTOR.toScreen(pt[0], pt[1]);
        d += (i === 0 ? 'M' : 'L') + px.toFixed(1) + ' ' + py.toFixed(1);
      }
    }
    if (!d) {
      continue;
    }
    if (riv.rank === 1) {
      trunkCasingPaths.push(d);
    }
    const rankClass =
      riv.rank === 1
        ? 'rank-trunk'
        : riv.rank === 2
          ? 'rank-major'
          : riv.rank <= 4
            ? 'rank-med'
            : 'rank-minor';
    rivers.push({ d, rankClass });
  }

  cachedHydroLayer = { lakes, trunkCasingPaths, rivers };
  return cachedHydroLayer;
}

export interface LayerLegendEntry {
  key: MapReportSeverity;
  shortLabel: string;
  detailLabel: string;
}

export function getLayerLegendEntries(layer: MapLayerKind): readonly LayerLegendEntry[] {
  if (layer === 'disaster') {
    return [
      { key: 'urgent', shortLabel: '水患', detailLabel: '朱砂红：水患告急' },
      { key: 'mild', shortLabel: '旱灾', detailLabel: '赭黄：旱灾轻灾' },
      { key: 'stable', shortLabel: '平稳', detailLabel: '青灰绿：本州平稳' },
      { key: 'unknown', shortLabel: '未奏报', detailLabel: '斜纹灰：本周未奏报（未知，绝非0）' },
      { key: 'background', shortLabel: '周边地域', detailLabel: '浅米灰：地理背景区（未启用）' },
    ];
  }
  if (layer === 'grain') {
    return [
      { key: 'urgent', shortLabel: '存粮匮乏', detailLabel: '朱砂红：可支配粮 ≤ 0万石' },
      { key: 'mild', shortLabel: '存粮偏紧', detailLabel: '赭黄：可支配粮 ≤ 1.0万石' },
      { key: 'stable', shortLabel: '存粮充裕', detailLabel: '青灰绿：可支配粮 > 1.0万石' },
      { key: 'unknown', shortLabel: '未奏报', detailLabel: '斜纹灰：本周未奏报（未知，绝非0）' },
      { key: 'background', shortLabel: '周边地域', detailLabel: '浅米灰：地理背景区（未启用）' },
    ];
  }
  return [
    { key: 'urgent', shortLabel: '存银匮乏', detailLabel: '朱砂红：可支配银 ≤ 0万两' },
    { key: 'mild', shortLabel: '存银偏紧', detailLabel: '赭黄：可支配银 ≤ 0.5万两' },
    { key: 'stable', shortLabel: '存银充裕', detailLabel: '青灰绿：可支配银 > 0.5万两' },
    { key: 'unknown', shortLabel: '未奏报', detailLabel: '斜纹灰：本周未奏报（未知，绝非0）' },
    { key: 'background', shortLabel: '周边地域', detailLabel: '浅米灰：地理背景区（未启用）' },
  ];
}

export interface StateLayerPresentation {
  severityKey: 'urgent' | 'mild' | 'stable' | 'unknown';
  badgeSubtitle: string;
}

export function computeStateLayerPresentation(
  state: CourtStateView,
  layer: MapLayerKind,
): StateLayerPresentation {
  if (state.report_status === 'UNKNOWN' || !state.report) {
    return {
      severityKey: 'unknown',
      badgeSubtitle: '本周未奏报（未知）',
    };
  }
  const rep = state.report;
  if (layer === 'disaster') {
    return {
      severityKey: rep.severity,
      badgeSubtitle:
        rep.relief_demand_grain > 0
          ? `${rep.disaster_label} · 需赈${formatWan(rep.relief_demand_grain, '万石')}`
          : `${rep.disaster_label} · 安稳`,
    };
  }
  if (layer === 'grain') {
    const sev =
      rep.disposable_grain <= 0
        ? 'urgent'
        : rep.disposable_grain <= 10_000
          ? 'mild'
          : 'stable';
    return {
      severityKey: sev,
      badgeSubtitle: `可支配粮 ${formatWan(rep.disposable_grain, '万石')}（账面${formatWan(rep.gross_grain, '万石')}）`,
    };
  }
  const sev =
    rep.disposable_silver <= 0
      ? 'urgent'
      : rep.disposable_silver <= 5_000
        ? 'mild'
        : 'stable';
  return {
    severityKey: sev,
    badgeSubtitle: `可支配银 ${formatWan(rep.disposable_silver, '万两')}（账面${formatWan(rep.gross_silver, '万两')}）`,
  };
}

export function pickDefaultSelectedState(states: CourtStateView[]): StateId {
  const urgentB = states.find((s) => s.state_id === 'state_b' && s.map_severity === 'urgent');
  if (urgentB) return 'state_b';
  const anyUrgent = states.find((s) => s.map_severity === 'urgent');
  if (anyUrgent) return anyUrgent.state_id;
  const anyMild = states.find((s) => s.map_severity === 'mild');
  if (anyMild) return anyMild.state_id;
  return 'state_b';
}

function computeSvgViewportTransform(
  camera: MapCameraState,
  viewportWidth = 1440,
  viewportHeight = Math.round((viewportWidth || 1440) * 0.625),
): {
  safeW: number;
  safeH: number;
  z: number;
  vw: number;
  vh: number;
  svgScale: number;
  padX: number;
  padY: number;
} {
  const safeW = Math.max(320, viewportWidth || 1440);
  const safeH = Math.max(240, viewportHeight || Math.round(safeW * 0.625));
  const z = Math.max(0.65, Math.min(2.6, camera.zoom || 1));
  const vw = MAP_VIEWBOX_WIDTH / z;
  const vh = MAP_VIEWBOX_HEIGHT / z;
  const scaleX = safeW / vw;
  const scaleY = safeH / vh;
  const svgScale = Math.max(scaleX, scaleY);
  const padX = (safeW - vw * svgScale) * 0.5;
  const padY = (safeH - vh * svgScale) * 0.5;
  return { safeW, safeH, z, vw, vh, svgScale, padX, padY };
}

export function getStateScreenPoint(
  stateId: StateId,
  viewportWidth: number,
  viewportHeight: number,
  camera: MapCameraState,
): { x: number; y: number; baseX: number; baseY: number } {
  const { safeW, safeH, svgScale, padX, padY } = computeSvgViewportTransform(
    camera,
    viewportWidth,
    viewportHeight,
  );
  const geom = PLAYABLE_PROVINCE_GEOMETRIES.find((p) => p.state_id === stateId);
  if (!geom) {
    return {
      x: safeW * 0.5,
      y: safeH * 0.5,
      baseX: safeW * 0.5,
      baseY: safeH * 0.5,
    };
  }
  const baseX = geom.center.x * svgScale + padX;
  const baseY = geom.center.y * svgScale + padY;
  return {
    x: baseX + camera.panX,
    y: baseY + camera.panY,
    baseX,
    baseY,
  };
}

export function getStateScreenCenterX(
  stateId: StateId,
  viewportWidth: number,
  camera: MapCameraState,
  viewportHeight = Math.round((viewportWidth || 1440) * 0.625),
): number {
  return getStateScreenPoint(stateId, viewportWidth, viewportHeight, camera).x;
}

export function getStateScreenCenterY(
  stateId: StateId,
  viewportWidth: number,
  viewportHeight: number,
  camera: MapCameraState,
): number {
  return getStateScreenPoint(stateId, viewportWidth, viewportHeight, camera).y;
}

/**
 * Computes the minimal 2D pan (`panX` and `panY`) required so the selected state's center/title
 * sits inside the unobstructed map corridor:
 * - Horizontally between the Left Sheet (`LEFT_SHEET_OCCLUSION_RATIO`) and Right Outliner (`RIGHT_OUTLINER_OCCLUSION_RATIO`)
 * - Vertically below the Top HUD Bar (`TOP_HUD_OCCLUSION_RATIO`) and above the Lower-Right Map Controls (`BOTTOM_CONTROLS_OCCLUSION_RATIO`)
 */
export function computeMinimalOcclusionPan(
  stateId: StateId,
  viewportWidth: number,
  currentCam: MapCameraState,
  drawerOpen: boolean,
  viewportHeight = Math.round((viewportWidth || 1440) * 0.625),
): MapCameraState {
  if (!drawerOpen || viewportWidth < 768) {
    return currentCam;
  }
  const geom = PLAYABLE_PROVINCE_GEOMETRIES.find((p) => p.state_id === stateId);
  if (!geom) {
    return currentCam;
  }

  const { safeW, safeH } = computeSvgViewportTransform(currentCam, viewportWidth, viewportHeight);
  const { x: currentScreenX, y: currentScreenY, baseX, baseY } = getStateScreenPoint(
    stateId,
    safeW,
    safeH,
    currentCam,
  );

  const minSafeX = LEFT_SHEET_OCCLUSION_RATIO * safeW;
  const maxSafeX = RIGHT_OUTLINER_OCCLUSION_RATIO * safeW;
  const minSafeY = TOP_HUD_OCCLUSION_RATIO * safeH;
  const maxSafeY = BOTTOM_CONTROLS_OCCLUSION_RATIO * safeH;

  let nextPanX = currentCam.panX;
  let nextPanY = currentCam.panY;

  if (currentScreenX < minSafeX) {
    const targetX = LEFT_SHEET_SAFE_TARGET_RATIO * safeW;
    nextPanX = Number((targetX - baseX).toFixed(2));
  } else if (currentScreenX > maxSafeX) {
    const targetX = RIGHT_OUTLINER_SAFE_TARGET_RATIO * safeW;
    nextPanX = Number((targetX - baseX).toFixed(2));
  }

  if (currentScreenY < minSafeY) {
    const targetY = TOP_HUD_SAFE_TARGET_RATIO * safeH;
    nextPanY = Number((targetY - baseY).toFixed(2));
  } else if (currentScreenY > maxSafeY) {
    const targetY = BOTTOM_CONTROLS_SAFE_TARGET_RATIO * safeH;
    nextPanY = Number((targetY - baseY).toFixed(2));
  }

  if (nextPanX === currentCam.panX && nextPanY === currentCam.panY) {
    return currentCam;
  }

  return {
    ...currentCam,
    panX: nextPanX,
    panY: nextPanY,
  };
}

/**
 * Computes the SVG `viewBox` string for `<svg viewBox={...} preserveAspectRatio="xMidYMid slice">`
 * so zooming and panning operate purely in SVG coordinate space (as in `jiangshan-map`'s `_applyCamera`),
 * keeping vector strokes and labels sharp at every zoom level while matching
 * `getStateScreenPoint` on both X and Y axes.
 */
export function computeSvgCameraViewBox(
  camera: MapCameraState,
  viewportWidth = 1440,
  viewportHeight = 900,
): string {
  const { vw, vh, svgScale } = computeSvgViewportTransform(camera, viewportWidth, viewportHeight);
  const vx = -(camera.panX / svgScale);
  const vy = -(camera.panY / svgScale);
  return `${vx.toFixed(2)} ${vy.toFixed(2)} ${vw.toFixed(2)} ${vh.toFixed(2)}`;
}

/**
 * Computes the updated `MapCameraState` when zooming around a client pointer `(clientX, clientY)`
 * so the geographic coordinate under the pointer stays anchored across all aspect ratios.
 */
export function zoomCameraAtClientPoint(
  currentCam: MapCameraState,
  nextZoomRaw: number,
  clientX: number,
  clientY: number,
  rect: { left: number; top: number; width: number; height: number },
): MapCameraState {
  const z0 = Math.max(0.65, Math.min(2.6, currentCam.zoom || 1));
  const z1 = Math.max(0.65, Math.min(2.6, Number(nextZoomRaw.toFixed(2))));
  const k = z1 / z0;
  const { padX, padY } = computeSvgViewportTransform(currentCam, rect.width, rect.height);
  const relX = clientX - rect.left - padX;
  const relY = clientY - rect.top - padY;
  const nextPanX = relX - (relX - currentCam.panX) * k;
  const nextPanY = relY - (relY - currentCam.panY) * k;
  return {
    panX: Math.round(nextPanX),
    panY: Math.round(nextPanY),
    zoom: z1,
  };
}
