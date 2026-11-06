import type {
  ActiveProvinceId,
  CharacterId,
  CharacterPublicView,
  CourtProvinceView,
  KnownFact,
  OfficeId,
  ProvinceId
} from '../src/contracts/gameplay';
import {
  JIANGSHAN_HYDRO_DATA,
  JIANGSHAN_MING_C_REGIONS,
  JIANGSHAN_MING_C_SNAPSHOT_ID,
  JIANGSHAN_MING_C_SOURCE_COMMIT,
  JIANGSHAN_PROVINCE_OUTLINES,
  type GeoCoord,
  type MingCRegionOutline
} from './jiangshan-geo-data';

export const PROVINCE_IDS: readonly ProvinceId[] = [
  'beizhili',
  'nanzhili',
  'shandong',
  'shanxi',
  'henan',
  'shaanxi',
  'sichuan',
  'huguang',
  'zhejiang',
  'jiangxi',
  'fujian',
  'guangdong',
  'guangxi',
  'yunnan',
  'guizhou'
] as const;

export const ACTIVE_PROVINCE_IDS: readonly ActiveProvinceId[] = [
  'shaanxi',
  'henan',
  'huguang'
] as const;

export const OFFICE_IDS: readonly OfficeId[] = [
  'governor_shaanxi',
  'governor_henan',
  'governor_huguang'
] as const;

export const PROVINCE_FOUR_COLOR_PALETTE = [
  '#c3b176',
  '#8da98f',
  '#c09280',
  '#9caabe'
] as const;

export const PROVINCE_BASE_COLOR_BY_ID: Readonly<Record<ProvinceId, string>> = {
  beizhili: '#c3b176',
  nanzhili: '#c09280',
  shandong: '#9caabe',
  shanxi: '#9caabe',
  sichuan: '#8da98f',
  zhejiang: '#c3b176',
  jiangxi: '#8da98f',
  fujian: '#9caabe',
  guangdong: '#c09280',
  guangxi: '#8da98f',
  yunnan: '#c3b176',
  guizhou: '#c09280',
  shaanxi: '#c09280',
  henan: '#8da98f',
  huguang: '#c3b176'
} as const;

export const PROVINCE_ADJACENT_PAIRS: ReadonlyArray<readonly [ProvinceId, ProvinceId]> = [
  ['beizhili', 'shanxi'],
  ['beizhili', 'henan'],
  ['beizhili', 'shandong'],
  ['nanzhili', 'shandong'],
  ['nanzhili', 'zhejiang'],
  ['sichuan', 'yunnan'],
  ['jiangxi', 'nanzhili'],
  ['jiangxi', 'zhejiang'],
  ['fujian', 'zhejiang'],
  ['fujian', 'jiangxi'],
  ['fujian', 'guangdong'],
  ['guangdong', 'huguang'],
  ['guangdong', 'jiangxi'],
  ['guangdong', 'guangxi'],
  ['guangxi', 'huguang'],
  ['guangxi', 'yunnan'],
  ['guangxi', 'guizhou'],
  ['guizhou', 'sichuan'],
  ['guizhou', 'huguang'],
  ['guizhou', 'yunnan'],
  ['shaanxi', 'shanxi'],
  ['shaanxi', 'sichuan'],
  ['henan', 'nanzhili'],
  ['henan', 'shandong'],
  ['henan', 'shanxi'],
  ['henan', 'shaanxi'],
  ['henan', 'huguang'],
  ['huguang', 'nanzhili'],
  ['huguang', 'shaanxi'],
  ['huguang', 'sichuan'],
  ['huguang', 'jiangxi']
] as const;

export function getProvinceBaseColor(provinceId: ProvinceId): string {
  return PROVINCE_BASE_COLOR_BY_ID[provinceId];
}

export type MapLayerKind = 'silver' | 'grain' | 'disaster';

export interface MapLayerMeta {
  id: MapLayerKind;
  label: string;
  shortLabel: string;
  unitLabel: string;
  legendLow: string;
  legendMid: string;
  legendHigh: string;
  legendUnknown: string;
}

export const MAP_LAYERS: readonly MapLayerMeta[] = [
  {
    id: 'silver',
    label: '藩库银图层',
    shortLabel: '存银',
    unitLabel: '万两',
    legendLow: '紧缺',
    legendMid: '适中',
    legendHigh: '充裕',
    legendUnknown: '未奏报'
  },
  {
    id: 'grain',
    label: '仓谷储量图层',
    shortLabel: '存粮',
    unitLabel: '万石',
    legendLow: '紧缺',
    legendMid: '常平',
    legendHigh: '充盈',
    legendUnknown: '未奏报'
  },
  {
    id: 'disaster',
    label: '灾情待赈图层',
    shortLabel: '灾情',
    unitLabel: '灾情',
    legendLow: '岁境平顺',
    legendMid: '灾荒待赈',
    legendHigh: '灾情深重',
    legendUnknown: '未奏报'
  }
] as const;

export const MAP_BASE_WIDTH = 1000;
export const MAP_BASE_HEIGHT = 700;
export const MAP_GEO_BOUNDS = {
  west: 66,
  east: 142,
  south: 14,
  north: 55
} as const;

// Focused viewport framing the Two Capitals and Thirteen Provinces (`s_ming_c`).
export const MAP_VIEWBOX_ORIGIN_X = 395;
export const MAP_VIEWBOX_ORIGIN_Y = 278;
export const MAP_VIEWBOX_WIDTH = 460;
export const MAP_VIEWBOX_HEIGHT = 288;

export const TERRAIN_RELIEF_RECT = {
  x: -80 - MAP_VIEWBOX_ORIGIN_X,
  y: -40 - MAP_VIEWBOX_ORIGIN_Y,
  width: 1160,
  height: 780
} as const;

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

export class MercatorProjector {
  readonly width: number;
  readonly height: number;
  readonly west: number;
  readonly east: number;
  readonly south: number;
  readonly north: number;
  readonly mercNorth: number;
  readonly mercSouth: number;
  readonly scaleX: number;
  readonly scaleY: number;

  constructor(
    width = MAP_BASE_WIDTH,
    height = MAP_BASE_HEIGHT,
    bounds = MAP_GEO_BOUNDS
  ) {
    this.width = width;
    this.height = height;
    this.west = bounds.west;
    this.east = bounds.east;
    this.south = bounds.south;
    this.north = bounds.north;
    this.mercNorth = this.latToMercY(this.north);
    this.mercSouth = this.latToMercY(this.south);
    this.scaleX = this.width / (this.east - this.west);
    this.scaleY = this.height / (this.mercNorth - this.mercSouth);
  }

  latToMercY(lat: number): number {
    const clamped = Math.max(-85, Math.min(85, lat));
    return Math.log(Math.tan(Math.PI / 4 + (clamped * DEG2RAD) / 2));
  }

  mercYToLat(mercY: number): number {
    return (2 * Math.atan(Math.exp(mercY)) - Math.PI / 2) * RAD2DEG;
  }

  toScreen(lon: number, lat: number): [number, number] {
    const x = (lon - this.west) * this.scaleX - MAP_VIEWBOX_ORIGIN_X;
    const mercY = this.latToMercY(lat);
    const y = (this.mercNorth - mercY) * this.scaleY - MAP_VIEWBOX_ORIGIN_Y;
    return [x, y];
  }

  toGeo(x: number, y: number): [number, number] {
    const baseX = x + MAP_VIEWBOX_ORIGIN_X;
    const baseY = y + MAP_VIEWBOX_ORIGIN_Y;
    const lon = this.west + baseX / this.scaleX;
    const mercY = this.mercNorth - baseY / this.scaleY;
    const lat = this.mercYToLat(mercY);
    return [lon, lat];
  }

  ringToSvgPath(ring: GeoCoord[], close = true): string {
    if (!ring || ring.length === 0) return '';
    let d = '';
    for (let i = 0; i < ring.length; i++) {
      const pt = ring[i];
      if (!pt) continue;
      const [x, y] = this.toScreen(pt[0], pt[1]);
      const cmd = i === 0 ? 'M' : 'L';
      d += `${cmd}${x.toFixed(1)},${y.toFixed(1)}`;
    }
    if (close) d += 'Z';
    return d;
  }

  smoothRingToSvgPath(ring: GeoCoord[], close = true, tension = 0.2): string {
    if (!ring || ring.length < 3) return this.ringToSvgPath(ring, close);
    const pts = ring.map((c) => this.toScreen(c[0], c[1]));
    const first = pts[0];
    const last = pts[pts.length - 1];
    if (
      pts.length > 3 &&
      first &&
      last &&
      Math.hypot(first[0] - last[0], first[1] - last[1]) < 1.5
    ) {
      pts.pop();
    }
    const n = pts.length;
    const startPt = pts[0];
    if (n < 3 || !startPt) return this.ringToSvgPath(ring, close);

    let d = `M${startPt[0].toFixed(1)},${startPt[1].toFixed(1)}`;
    const limit = close ? n : n - 1;
    for (let i = 0; i < limit; i++) {
      const p0 = pts[(i - 1 + n) % n]!;
      const p1 = pts[i]!;
      const p2 = pts[(i + 1) % n]!;
      const p3 = pts[(i + 2) % n]!;

      const cp1x = p1[0] + (p2[0] - p0[0]) * tension;
      const cp1y = p1[1] + (p2[1] - p0[1]) * tension;
      const cp2x = p2[0] - (p3[0] - p1[0]) * tension;
      const cp2y = p2[1] - (p3[1] - p1[1]) * tension;

      d += ` C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
    }
    if (close) d += 'Z';
    return d;
  }
}

export const JIANGSHAN_PROJECTOR = new MercatorProjector();

export function projectGeoPoint(lon: number, lat: number): { x: number; y: number } {
  const [x, y] = JIANGSHAN_PROJECTOR.toScreen(lon, lat);
  return {
    x: Number(x.toFixed(1)),
    y: Number(y.toFixed(1))
  };
}

/**
 * Explicit mapping between Jiangshan `s_ming_c` (`1636–1643`) provider feature IDs
 * and the 15 authoritative game `ProvinceId` values.
 * Provider IDs are never used directly as character or province identities.
 */
export const PROVIDER_REGION_ID_TO_PROVINCE_ID: Readonly<Record<number, ProvinceId>> = {
  1113: 'beizhili',
  1077: 'nanzhili',
  1078: 'shandong',
  1079: 'shanxi',
  1080: 'henan',
  1081: 'shaanxi',
  1082: 'sichuan',
  1083: 'huguang',
  1084: 'zhejiang',
  1085: 'jiangxi',
  1086: 'fujian',
  1087: 'guangdong',
  1088: 'guangxi',
  1089: 'yunnan',
  1090: 'guizhou'
} as const;

export const PROVINCE_ID_TO_PROVIDER_REGION_ID: Readonly<Record<ProvinceId, number>> = {
  beizhili: 1113,
  nanzhili: 1077,
  shandong: 1078,
  shanxi: 1079,
  henan: 1080,
  shaanxi: 1081,
  sichuan: 1082,
  huguang: 1083,
  zhejiang: 1084,
  jiangxi: 1085,
  fujian: 1086,
  guangdong: 1087,
  guangxi: 1088,
  yunnan: 1089,
  guizhou: 1090
} as const;

const ACTIVE_PROVINCE_SET: ReadonlySet<string> = new Set<string>(ACTIVE_PROVINCE_IDS);
const ALL_PROVINCE_SET: ReadonlySet<string> = new Set<string>(PROVINCE_IDS);

export function isProvinceId(value: string): value is ProvinceId {
  return ALL_PROVINCE_SET.has(value);
}

export function isActiveProvinceId(value: string): value is ActiveProvinceId {
  return ACTIVE_PROVINCE_SET.has(value);
}

export function resolveProvinceIdFromProviderId(providerId: number | string): ProvinceId | null {
  const numericId = typeof providerId === 'number' ? providerId : Number(providerId);
  if (!Number.isInteger(numericId)) {
    return null;
  }
  return PROVIDER_REGION_ID_TO_PROVINCE_ID[numericId] ?? null;
}

export function resolveProviderIdFromProvinceId(provinceId: ProvinceId): number {
  return PROVINCE_ID_TO_PROVIDER_REGION_ID[provinceId];
}

export interface TownMarker {
  name: string;
  x: number;
  y: number;
  dx: number;
  dy: number;
  isCapital?: boolean;
}

export interface ProjectedMingPrefecture {
  provider_id: number;
  title: string;
  category: string;
  x: number;
  y: number;
}

export interface MingProvinceGeometry {
  province_id: ProvinceId;
  provider_region_id: number;
  ring_ids: number[];
  snapshot_id: string;
  source_commit: string;
  name: string;
  category: '直隶' | '布政使司';
  active: boolean;
  seat_name: string;
  jurisdiction_summary: string;
  outerPath: string;
  labelCenterX: number;
  labelCenterY: number;
  capitalX: number;
  capitalY: number;
  prefectures: ProjectedMingPrefecture[];
  towns: TownMarker[];
}

// Interior label anchors tuned so all 15 labels sit cleanly inside their `s_ming_c` polygons
// and the 3 active provinces (`shaanxi`, `henan`, `huguang`) sit inside the unobstructed
// central corridor `[34%, 74%] × [18%, 78%]` at `INITIAL_MAP_CAMERA`.
const PROVINCE_LABEL_GEO_ANCHORS: Readonly<Record<ProvinceId, GeoCoord>> = {
  shaanxi: [108.6, 35.1],
  henan: [113.5, 34.0],
  huguang: [112.3, 29.8],
  beizhili: [115.68, 38.91],
  nanzhili: [118.31, 32.16],
  shandong: [118.29, 36.44],
  shanxi: [112.33, 37.72],
  sichuan: [105.62, 30.25],
  zhejiang: [120.1, 29.17],
  jiangxi: [115.69, 27.62],
  fujian: [118.01, 26.07],
  guangdong: [113.1, 23.2],
  guangxi: [108.79, 23.82],
  yunnan: [101.8, 25.1],
  guizhou: [106.89, 26.86]
};

function buildMingCRegionPath(region: MingCRegionOutline): string {
  let d = '';
  for (const poly of region.rings) {
    for (const ring of poly) {
      d += JIANGSHAN_PROJECTOR.ringToSvgPath(ring, true);
    }
  }
  return d;
}

function buildMingInteriorBoundaryPath(regions: readonly MingCRegionOutline[]): string {
  const quantize = (pt: GeoCoord) => `${Math.round(pt[0] * 100)},${Math.round(pt[1] * 100)}`;
  const directedEdges = new Set<string>();
  const rawSegments: Array<[GeoCoord, GeoCoord]> = [];

  for (const reg of regions) {
    for (const poly of reg.rings) {
      for (const ring of poly) {
        if (!ring || ring.length < 2) continue;
        for (let i = 0; i < ring.length - 1; i++) {
          const a = ring[i];
          const b = ring[i + 1];
          if (!a || !b) continue;
          const ka = quantize(a);
          const kb = quantize(b);
          if (ka === kb) continue;
          directedEdges.add(`${ka}>${kb}`);
          rawSegments.push([a, b]);
        }
      }
    }
  }

  const emittedUndirected = new Set<string>();
  let interiorD = '';
  for (const [a, b] of rawSegments) {
    const ka = quantize(a);
    const kb = quantize(b);
    const undirectedKey = ka < kb ? `${ka}|${kb}` : `${kb}|${ka}`;
    if (emittedUndirected.has(undirectedKey)) continue;
    const isShared = directedEdges.has(`${ka}>${kb}`) && directedEdges.has(`${kb}>${ka}`);
    if (!isShared) continue;
    emittedUndirected.add(undirectedKey);
    const [x1, y1] = JIANGSHAN_PROJECTOR.toScreen(a[0], a[1]);
    const [x2, y2] = JIANGSHAN_PROJECTOR.toScreen(b[0], b[1]);
    interiorD += `M${x1.toFixed(1)},${y1.toFixed(1)}L${x2.toFixed(1)},${y2.toFixed(1)}`;
  }

  return interiorD;
}

function buildMingProvinceGeometries(): MingProvinceGeometry[] {
  const byProviderId = new Map<number, MingCRegionOutline>(
    JIANGSHAN_MING_C_REGIONS.map((region) => [region.providerId, region])
  );

  // Order provinces with the 12 frozen provinces first and the 3 active provinces last
  // so active borders and badges paint cleanly above frozen neighbors.
  const orderedProvinceIds: ProvinceId[] = [
    ...PROVINCE_IDS.filter((id: ProvinceId) => !isActiveProvinceId(id)),
    ...ACTIVE_PROVINCE_IDS
  ];

  return orderedProvinceIds.map((provinceId) => {
    const providerId = PROVINCE_ID_TO_PROVIDER_REGION_ID[provinceId];
    const region = byProviderId.get(providerId);
    if (!region) {
      throw new Error(`Missing s_ming_c region for providerId=${providerId} (${provinceId})`);
    }

    const active = isActiveProvinceId(provinceId);
    const labelGeo = PROVINCE_LABEL_GEO_ANCHORS[provinceId] ?? region.anchor;
    const labelPt = projectGeoPoint(labelGeo[0], labelGeo[1]);

    const projectedPrefectures: ProjectedMingPrefecture[] = region.prefectures.map((pref) => {
      const pt = projectGeoPoint(pref.anchor[0], pref.anchor[1]);
      return {
        provider_id: pref.providerId,
        title: pref.title,
        category: pref.cat,
        x: pt.x,
        y: pt.y
      };
    });

    const seatPref =
      projectedPrefectures.find((p) => p.title === region.seat) ??
      projectedPrefectures[0] ?? {
        provider_id: providerId,
        title: region.seat,
        category: '府',
        x: labelPt.x,
        y: labelPt.y - 6
      };

    const samplePrefs = projectedPrefectures.slice(0, 4).map((p) => p.title);
    const jurisdictionSummary =
      projectedPrefectures.length > 0
        ? `治所${region.seat}，下辖${samplePrefs.join('、')}${projectedPrefectures.length > 4 ? `等${projectedPrefectures.length}府州` : `共${projectedPrefectures.length}府州`}`
        : `治所${region.seat}`;

    const towns: TownMarker[] = [
      {
        name: region.seat,
        x: seatPref.x,
        y: seatPref.y,
        dx: 6,
        dy: -5,
        isCapital: true
      },
      ...projectedPrefectures
        .filter((p) => p.title !== region.seat)
        .slice(0, active ? 5 : 2)
        .map((p, idx) => ({
          name: p.title,
          x: p.x,
          y: p.y,
          dx: idx % 2 === 0 ? 5 : -24,
          dy: idx % 2 === 0 ? 9 : -5
        }))
    ];

    return {
      province_id: provinceId,
      provider_region_id: providerId,
      ring_ids: region.ringIds,
      snapshot_id: JIANGSHAN_MING_C_SNAPSHOT_ID,
      source_commit: JIANGSHAN_MING_C_SOURCE_COMMIT,
      name: region.title,
      category: region.cat,
      active,
      seat_name: region.seat,
      jurisdiction_summary: jurisdictionSummary,
      outerPath: buildMingCRegionPath(region),
      labelCenterX: labelPt.x,
      labelCenterY: labelPt.y,
      capitalX: seatPref.x,
      capitalY: seatPref.y,
      prefectures: projectedPrefectures,
      towns
    };
  });
}

export const MING_PROVINCE_GEOMETRIES: readonly MingProvinceGeometry[] = buildMingProvinceGeometries();

export const MING_PROVINCE_GEOMETRY_BY_ID: Readonly<Record<ProvinceId, MingProvinceGeometry>> =
  Object.fromEntries(
    MING_PROVINCE_GEOMETRIES.map((g) => [g.province_id, g])
  ) as Record<ProvinceId, MingProvinceGeometry>;

export const MING_INTERIOR_BOUNDARY_PATH: string = buildMingInteriorBoundaryPath(
  JIANGSHAN_MING_C_REGIONS
);

export interface JiangshanProjectedRiver {
  name: string;
  rank: number;
  path: string;
}

export interface JiangshanProjectedLake {
  name: string;
  rank: number;
  path: string;
}

export interface JiangshanProjectedHydroLabel {
  zh: string;
  kind: 'trunk' | 'river' | 'lake';
  x: number;
  y: number;
  rot: number;
}

export interface JiangshanBackgroundMapGeometry {
  outerLandPath: string;
  interiorBordersPath: string;
  rivers: JiangshanProjectedRiver[];
  lakes: JiangshanProjectedLake[];
  hydroLabels: JiangshanProjectedHydroLabel[];
}

function buildJiangshanBackgroundMap(): JiangshanBackgroundMapGeometry {
  const quantize = (pt: GeoCoord) => `${Math.round(pt[0] * 100)},${Math.round(pt[1] * 100)}`;
  const directedEdges = new Set<string>();
  const rawSegments: Array<[GeoCoord, GeoCoord]> = [];

  for (const prov of JIANGSHAN_PROVINCE_OUTLINES) {
    for (const poly of prov.rings) {
      for (const ring of poly) {
        if (!ring || ring.length < 2) continue;
        for (let i = 0; i < ring.length - 1; i++) {
          const a = ring[i];
          const b = ring[i + 1];
          if (!a || !b) continue;
          const ka = quantize(a);
          const kb = quantize(b);
          if (ka === kb) continue;
          directedEdges.add(`${ka}>${kb}`);
          rawSegments.push([a, b]);
        }
      }
    }
  }

  const emittedUndirected = new Set<string>();
  let outerD = '';
  let interiorD = '';

  for (const [a, b] of rawSegments) {
    const ka = quantize(a);
    const kb = quantize(b);
    const undirectedKey = ka < kb ? `${ka}|${kb}` : `${kb}|${ka}`;
    if (emittedUndirected.has(undirectedKey)) continue;
    emittedUndirected.add(undirectedKey);

    const isShared = directedEdges.has(`${ka}>${kb}`) && directedEdges.has(`${kb}>${ka}`);
    const [x1, y1] = JIANGSHAN_PROJECTOR.toScreen(a[0], a[1]);
    const [x2, y2] = JIANGSHAN_PROJECTOR.toScreen(b[0], b[1]);
    const seg = `M${x1.toFixed(1)},${y1.toFixed(1)}L${x2.toFixed(1)},${y2.toFixed(1)}`;
    if (isShared) {
      interiorD += seg;
    } else {
      outerD += seg;
    }
  }

  let landFillD = '';
  for (const prov of JIANGSHAN_PROVINCE_OUTLINES) {
    for (const poly of prov.rings) {
      for (const ring of poly) {
        landFillD += JIANGSHAN_PROJECTOR.ringToSvgPath(ring, true);
      }
    }
  }

  // Use 1636 historical reference year so Ming-era Yellow River taking the Huai course (1194–1855) is shown.
  const referenceYear = 1636;
  const rivers: JiangshanProjectedRiver[] = [];
  for (const r of JIANGSHAN_HYDRO_DATA.rivers) {
    if (r.appear !== undefined && referenceYear < r.appear) continue;
    if (r.vanish !== undefined && referenceYear > r.vanish) continue;
    if (r.rank > 4) continue;
    let d = '';
    for (const line of r.lines) {
      d += `${JIANGSHAN_PROJECTOR.smoothRingToSvgPath(line, false, 0.22)} `;
    }
    const trimmed = d.trim();
    if (trimmed) {
      rivers.push({ name: r.name, rank: r.rank, path: trimmed });
    }
  }

  const lakes: JiangshanProjectedLake[] = [];
  for (const l of JIANGSHAN_HYDRO_DATA.lakes) {
    if (l.appear !== undefined && referenceYear < l.appear) continue;
    if (l.vanish !== undefined && referenceYear > l.vanish) continue;
    if (l.rank > 3) continue;
    let d = '';
    for (const ring of l.rings) {
      d += `${JIANGSHAN_PROJECTOR.smoothRingToSvgPath(ring, true, 0.18)} `;
    }
    const trimmed = d.trim();
    if (trimmed) {
      lakes.push({ name: l.name, rank: l.rank, path: trimmed });
    }
  }

  const hydroLabels: JiangshanProjectedHydroLabel[] = [];
  for (const lb of JIANGSHAN_HYDRO_DATA.labels) {
    if (lb.appear !== undefined && referenceYear < lb.appear) continue;
    if (lb.vanish !== undefined && referenceYear > lb.vanish) continue;
    const [x, y] = JIANGSHAN_PROJECTOR.toScreen(lb.coord[0], lb.coord[1]);
    if (x < -120 || x > MAP_VIEWBOX_WIDTH + 120 || y < -120 || y > MAP_VIEWBOX_HEIGHT + 120) {
      continue;
    }
    hydroLabels.push({
      zh: lb.zh,
      kind: lb.kind,
      x: Number(x.toFixed(1)),
      y: Number(y.toFixed(1)),
      rot: lb.rot ?? 0
    });
  }

  return {
    outerLandPath: landFillD || outerD,
    interiorBordersPath: interiorD,
    rivers,
    lakes,
    hydroLabels
  };
}

export const JIANGSHAN_BACKGROUND_MAP: JiangshanBackgroundMapGeometry = buildJiangshanBackgroundMap();

export interface MapCamera {
  panX: number;
  panY: number;
  zoom: number;
}

export const INITIAL_MAP_CAMERA: MapCamera = {
  panX: 0,
  panY: 0,
  zoom: 1
};

export const MIN_MAP_ZOOM = 0.78;
export const MAX_MAP_ZOOM = 2.6;

export function clampZoom(zoom: number): number {
  if (!Number.isFinite(zoom)) return 1;
  return Math.min(MAX_MAP_ZOOM, Math.max(MIN_MAP_ZOOM, Number(zoom.toFixed(3))));
}

export function computeSvgViewBox(
  camera: MapCamera,
  viewportWidth = 1440,
  viewportHeight = 900
): { x: number; y: number; width: number; height: number; viewBoxString: string } {
  const safeVw = Math.max(320, viewportWidth);
  const safeVh = Math.max(240, viewportHeight);
  const zoom = clampZoom(camera.zoom);

  const scaleX = safeVw / MAP_VIEWBOX_WIDTH;
  const scaleY = safeVh / MAP_VIEWBOX_HEIGHT;
  const baseScale = Math.min(scaleX, scaleY) * zoom;

  const width = safeVw / baseScale;
  const height = safeVh / baseScale;

  const centerX = MAP_VIEWBOX_WIDTH / 2 - camera.panX;
  const centerY = MAP_VIEWBOX_HEIGHT / 2 - camera.panY;

  const x = centerX - width / 2;
  const y = centerY - height / 2;

  return {
    x,
    y,
    width,
    height,
    viewBoxString: `${x.toFixed(2)} ${y.toFixed(2)} ${width.toFixed(2)} ${height.toFixed(2)}`
  };
}

export function zoomCameraAtScreenPoint(
  camera: MapCamera,
  nextZoomRaw: number,
  cursorScreenX: number,
  cursorScreenY: number,
  viewportWidth: number,
  viewportHeight: number
): MapCamera {
  const nextZoom = clampZoom(nextZoomRaw);
  const prevBox = computeSvgViewBox(camera, viewportWidth, viewportHeight);
  const safeVw = Math.max(320, viewportWidth);
  const safeVh = Math.max(240, viewportHeight);

  const normX = Math.min(1, Math.max(0, cursorScreenX / safeVw));
  const normY = Math.min(1, Math.max(0, cursorScreenY / safeVh));

  const worldX = prevBox.x + normX * prevBox.width;
  const worldY = prevBox.y + normY * prevBox.height;

  const scaleX = safeVw / MAP_VIEWBOX_WIDTH;
  const scaleY = safeVh / MAP_VIEWBOX_HEIGHT;
  const nextScale = Math.min(scaleX, scaleY) * nextZoom;
  const nextWidth = safeVw / nextScale;
  const nextHeight = safeVh / nextScale;

  const nextX = worldX - normX * nextWidth;
  const nextY = worldY - normY * nextHeight;

  const nextCenterX = nextX + nextWidth / 2;
  const nextCenterY = nextY + nextHeight / 2;

  const rawPanX = MAP_VIEWBOX_WIDTH / 2 - nextCenterX;
  const rawPanY = MAP_VIEWBOX_HEIGHT / 2 - nextCenterY;

  return {
    zoom: nextZoom,
    panX: Math.max(-220, Math.min(220, Number(rawPanX.toFixed(2)))),
    panY: Math.max(-160, Math.min(160, Number(rawPanY.toFixed(2))))
  };
}

export function panCameraByScreenDelta(
  camera: MapCamera,
  deltaScreenX: number,
  deltaScreenY: number,
  viewportWidth: number,
  viewportHeight: number
): MapCamera {
  const box = computeSvgViewBox(camera, viewportWidth, viewportHeight);
  const safeVw = Math.max(320, viewportWidth);
  const safeVh = Math.max(240, viewportHeight);

  const worldPerPixelX = box.width / safeVw;
  const worldPerPixelY = box.height / safeVh;

  const nextPanX = camera.panX + deltaScreenX * worldPerPixelX;
  const nextPanY = camera.panY + deltaScreenY * worldPerPixelY;

  return {
    ...camera,
    panX: Math.max(-220, Math.min(220, Number(rawPanClamped(nextPanX, -220, 220)))),
    panY: Math.max(-160, Math.min(160, Number(rawPanClamped(nextPanY, -160, 160))))
  };
}

function rawPanClamped(val: number, min: number, max: number): string {
  return Math.max(min, Math.min(max, val)).toFixed(2);
}

export function getProvinceScreenPoint(
  provinceId: ProvinceId,
  camera: MapCamera,
  viewportWidth: number,
  viewportHeight: number
): { x: number; y: number } {
  const geom = MING_PROVINCE_GEOMETRY_BY_ID[provinceId];
  if (!geom) return { x: viewportWidth / 2, y: viewportHeight / 2 };

  const box = computeSvgViewBox(camera, viewportWidth, viewportHeight);
  const normX = (geom.labelCenterX - box.x) / box.width;
  const normY = (geom.labelCenterY - box.y) / box.height;

  return {
    x: normX * viewportWidth,
    y: normY * viewportHeight
  };
}

export function getProvinceScreenCenterX(
  provinceId: ProvinceId,
  camera: MapCamera,
  viewportWidth: number,
  viewportHeight = 900
): number {
  return getProvinceScreenPoint(provinceId, camera, viewportWidth, viewportHeight).x;
}

export function getProvinceScreenCenterY(
  provinceId: ProvinceId,
  camera: MapCamera,
  viewportWidth = 1440,
  viewportHeight = 900
): number {
  return getProvinceScreenPoint(provinceId, camera, viewportWidth, viewportHeight).y;
}

export const getStateScreenPoint = getProvinceScreenPoint;
export const getStateScreenCenterX = getProvinceScreenCenterX;
export const getStateScreenCenterY = getProvinceScreenCenterY;

/**
 * Computes a minimal camera pan only if the selected province's screen center would
 * be occluded by the opened left work panel or the right edge HUD.
 */
export function computeMinimalOcclusionPan(
  provinceId: ProvinceId,
  camera: MapCamera,
  viewportWidth: number,
  viewportHeight = 900,
  leftPanelWidthPx = 416
): MapCamera {
  if (viewportWidth <= 960) {
    return camera;
  }
  const pt = getProvinceScreenPoint(provinceId, camera, viewportWidth, viewportHeight);
  const leftSafeX = leftPanelWidthPx + 36;
  const rightSafeX = viewportWidth - 280;

  let shiftScreenX = 0;
  if (pt.x < leftSafeX) {
    shiftScreenX = leftSafeX - pt.x;
  } else if (pt.x > rightSafeX) {
    shiftScreenX = rightSafeX - pt.x;
  }

  if (Math.abs(shiftScreenX) < 1) {
    return camera;
  }

  return panCameraByScreenDelta(camera, shiftScreenX, 0, viewportWidth, viewportHeight);
}

export type LayerSeverityBand = 'low' | 'medium' | 'high' | 'unknown' | 'frozen';

export interface ProvinceLayerPresentation {
  province_id: ProvinceId;
  active: boolean;
  band: LayerSeverityBand;
  fillColor: string;
  strokeColor: string;
  hatchPatternId: string | null;
  metricText: string;
  badgeText: string;
  valueWan: number | null;
  isKnown: boolean;
  isStaleFact: boolean;
  factTurnNumber: number | null;
  factAuthorId: CharacterId | null;
}

export function formatWanNumber(valueWan: number): string {
  if (!Number.isFinite(valueWan)) return '0.0';
  const rounded = Math.round(valueWan * 10) / 10;
  return rounded.toFixed(1);
}

export function formatSilverAmountWan(silverLiang: number): string {
  return `${formatWanNumber(silverLiang / 10000)}万两`;
}

export function formatGrainAmountWan(grainShi: number): string {
  return `${formatWanNumber(grainShi / 10000)}万石`;
}

export function formatPopulationCount(population: number): string {
  if (!Number.isFinite(population)) return '0人';
  if (population === 0) return '0人';
  if (population >= 10000) {
    return `${formatWanNumber(population / 10000)}万人`;
  }
  return `${Math.round(population).toLocaleString('zh-CN')}人`;
}

export function getNumericFactValue(fact: KnownFact | undefined): number | undefined {
  if (!fact || typeof fact.value !== 'number') return undefined;
  return fact.value;
}

export function getStringFactValue(fact: KnownFact | undefined): string | undefined {
  if (!fact || typeof fact.value !== 'string') return undefined;
  return fact.value;
}

export function formatKnownNumericFact(
  fact: KnownFact | undefined,
  unit: 'silver' | 'grain' | 'population'
): string {
  const num = getNumericFactValue(fact);
  if (num === undefined) {
    return '未奏报';
  }
  if (unit === 'silver') {
    return formatSilverAmountWan(num);
  }
  if (unit === 'grain') {
    return formatGrainAmountWan(num);
  }
  return formatPopulationCount(num);
}

export function formatFactProvenanceTag(
  fact: KnownFact | undefined,
  viewedTurnNumber: number,
  characterById?: ReadonlyMap<CharacterId, CharacterPublicView>
): { label: string; isStale: boolean; authorName: string | null; dateText: string | null } {
  if (fact === undefined) {
    return {
      label: '',
      isStale: false,
      authorName: null,
      dateText: null
    };
  }
  const authorName = characterById?.get(fact.author_character_id)?.name ?? fact.author_character_id;
  const dateText = formatTurnCalendarDate(fact.turn_number, fact.date);
  const isStale = fact.turn_number < viewedTurnNumber;
  return {
    label: isStale
      ? `往期记录 ${dateText} ${authorName}奏`
      : `本轮奏报 ${dateText} ${authorName}奏`,
    isStale,
    authorName,
    dateText
  };
}

/**
 * Computes map layer presentation strictly from `CourtProvinceView.known` (`KnownFacts`)
 * and `province.active`.
 * - Frozen provinces (`!active`) return `band: 'frozen'` and never invent metrics.
 * - Omitted known fields (`undefined`) return `band: 'unknown'` (`未奏报`).
 * - Explicit `0` values (`value === 0`) are known facts (`0.0万两` / `0.0万石` / `0人`), never `'unknown'`.
 */
export function computeProvinceLayerPresentation(
  provinceView: CourtProvinceView | undefined,
  layer: MapLayerKind,
  viewedTurnNumber?: number
): ProvinceLayerPresentation {
  if (!provinceView || !provinceView.province.active) {
    const pid = provinceView?.province.province_id ?? 'beizhili';
    const baseColor = PROVINCE_BASE_COLOR_BY_ID[pid];
    return {
      province_id: pid,
      active: false,
      band: 'frozen',
      fillColor: baseColor,
      strokeColor: '#8d8373',
      hatchPatternId: null,
      metricText: '冻结',
      badgeText: '冻结',
      valueWan: null,
      isKnown: false,
      isStaleFact: false,
      factTurnNumber: null,
      factAuthorId: null
    };
  }

  const pid = provinceView.province.province_id;
  const baseColor = PROVINCE_BASE_COLOR_BY_ID[pid];
  const known = provinceView.known;

  if (layer === 'silver') {
    const fact = known.gross_silver;
    const val = getNumericFactValue(fact);
    if (!fact || val === undefined) {
      return {
        province_id: pid,
        active: true,
        band: 'unknown',
        fillColor: baseColor,
        strokeColor: '#756a5a',
        hatchPatternId: 'hatch-unknown',
        metricText: '存银 未奏报',
        badgeText: '未奏报',
        valueWan: null,
        isKnown: false,
        isStaleFact: false,
        factTurnNumber: null,
        factAuthorId: null
      };
    }

    const valueWan = val / 10000;
    const isStaleFact = viewedTurnNumber !== undefined ? fact.turn_number < viewedTurnNumber : false;
    const staleSuffix = isStaleFact ? ` 第${fact.turn_number}轮旧档` : '';

    if (val >= 20_000) {
      return {
        province_id: pid,
        active: true,
        band: 'high',
        fillColor: baseColor,
        strokeColor: '#3f5f3c',
        hatchPatternId: null,
        metricText: `存银 ${formatWanNumber(valueWan)}万两${staleSuffix}`,
        badgeText: '藩库充裕',
        valueWan,
        isKnown: true,
        isStaleFact,
        factTurnNumber: fact.turn_number,
        factAuthorId: fact.author_character_id
      };
    }

    if (val >= 10_000) {
      return {
        province_id: pid,
        active: true,
        band: 'medium',
        fillColor: baseColor,
        strokeColor: '#6d5b34',
        hatchPatternId: 'hatch-medium',
        metricText: `存银 ${formatWanNumber(valueWan)}万两${staleSuffix}`,
        badgeText: '藩库适中',
        valueWan,
        isKnown: true,
        isStaleFact,
        factTurnNumber: fact.turn_number,
        factAuthorId: fact.author_character_id
      };
    }

    return {
      province_id: pid,
      active: true,
      band: 'low',
      fillColor: baseColor,
      strokeColor: '#7d3a2c',
      hatchPatternId: 'hatch-severe',
      metricText: `存银 ${formatWanNumber(valueWan)}万两${staleSuffix}`,
      badgeText: '藩库紧缺',
      valueWan,
      isKnown: true,
      isStaleFact,
      factTurnNumber: fact.turn_number,
      factAuthorId: fact.author_character_id
    };
  }

  if (layer === 'grain') {
    const fact = known.gross_grain;
    const val = getNumericFactValue(fact);
    if (!fact || val === undefined) {
      return {
        province_id: pid,
        active: true,
        band: 'unknown',
        fillColor: baseColor,
        strokeColor: '#756a5a',
        hatchPatternId: 'hatch-unknown',
        metricText: '存粮 未奏报',
        badgeText: '未奏报',
        valueWan: null,
        isKnown: false,
        isStaleFact: false,
        factTurnNumber: null,
        factAuthorId: null
      };
    }

    const valueWan = val / 10000;
    const isStaleFact = viewedTurnNumber !== undefined ? fact.turn_number < viewedTurnNumber : false;
    const staleSuffix = isStaleFact ? ` 第${fact.turn_number}轮旧档` : '';

    if (val >= 20_000) {
      return {
        province_id: pid,
        active: true,
        band: 'high',
        fillColor: baseColor,
        strokeColor: '#3f5f3c',
        hatchPatternId: null,
        metricText: `存粮 ${formatWanNumber(valueWan)}万石${staleSuffix}`,
        badgeText: '仓廪充盈',
        valueWan,
        isKnown: true,
        isStaleFact,
        factTurnNumber: fact.turn_number,
        factAuthorId: fact.author_character_id
      };
    }

    if (val >= 10_000) {
      return {
        province_id: pid,
        active: true,
        band: 'medium',
        fillColor: baseColor,
        strokeColor: '#6d5b34',
        hatchPatternId: 'hatch-medium',
        metricText: `存粮 ${formatWanNumber(valueWan)}万石${staleSuffix}`,
        badgeText: '仓储常平',
        valueWan,
        isKnown: true,
        isStaleFact,
        factTurnNumber: fact.turn_number,
        factAuthorId: fact.author_character_id
      };
    }

    return {
      province_id: pid,
      active: true,
      band: 'low',
      fillColor: baseColor,
      strokeColor: '#7d3a2c',
      hatchPatternId: 'hatch-severe',
      metricText: `存粮 ${formatWanNumber(valueWan)}万石${staleSuffix}`,
      badgeText: '仓储紧缺',
      valueWan,
      isKnown: true,
      isStaleFact,
      factTurnNumber: fact.turn_number,
      factAuthorId: fact.author_character_id
    };
  }

  // layer === 'disaster'
  const labelFact = known.disaster_label ?? known.disaster_type;
  const popFact = known.relief_population;
  const demandFact = known.relief_demand_grain;

  if (labelFact === undefined && popFact === undefined && demandFact === undefined) {
    return {
      province_id: pid,
      active: true,
      band: 'unknown',
      fillColor: baseColor,
      strokeColor: '#756a5a',
      hatchPatternId: 'hatch-unknown',
      metricText: '灾情 未奏报',
      badgeText: '未奏报',
      valueWan: null,
      isKnown: false,
      isStaleFact: false,
      factTurnNumber: null,
      factAuthorId: null
    };
  }

  const primaryFact = (popFact ?? demandFact ?? labelFact)!;
  const isStaleFact =
    viewedTurnNumber !== undefined ? primaryFact.turn_number < viewedTurnNumber : false;
  const staleSuffix = isStaleFact ? ` 第${primaryFact.turn_number}轮旧档` : '';
  const labelStr = getStringFactValue(known.disaster_label) ?? '灾情';
  const popCount = getNumericFactValue(popFact);
  const demandShi = getNumericFactValue(demandFact);

  const isSevere =
    (popCount !== undefined && popCount >= 25_000) ||
    (demandShi !== undefined && demandShi >= 25_000);
  const isCalm =
    !isSevere &&
    ((popCount !== undefined && popCount === 0 && (demandShi === undefined || demandShi === 0)) ||
      (popCount === undefined &&
        demandShi === 0 &&
        (labelFact === undefined ||
          labelStr === '无灾' ||
          getStringFactValue(known.disaster_type) === 'none')) ||
      (popCount === undefined &&
        demandShi === undefined &&
        (labelStr === '无灾' || getStringFactValue(known.disaster_type) === 'none')));

  const detailStr =
    popCount !== undefined
      ? `饥民${formatPopulationCount(popCount)}`
      : demandShi !== undefined
        ? `需粮${formatGrainAmountWan(demandShi)}`
        : '';

  const metricText = `${labelStr}${detailStr ? ` ${detailStr}` : ''}${staleSuffix}`;

  if (isSevere) {
    return {
      province_id: pid,
      active: true,
      band: 'high',
      fillColor: baseColor,
      strokeColor: '#7d3a2c',
      hatchPatternId: 'hatch-severe',
      metricText,
      badgeText: '灾情深重',
      valueWan: popCount !== undefined ? popCount / 10000 : null,
      isKnown: true,
      isStaleFact,
      factTurnNumber: primaryFact.turn_number,
      factAuthorId: primaryFact.author_character_id
    };
  }

  if (isCalm) {
    return {
      province_id: pid,
      active: true,
      band: 'low',
      fillColor: baseColor,
      strokeColor: '#3f5f3c',
      hatchPatternId: null,
      metricText,
      badgeText: '岁境平顺',
      valueWan: 0,
      isKnown: true,
      isStaleFact,
      factTurnNumber: primaryFact.turn_number,
      factAuthorId: primaryFact.author_character_id
    };
  }

  return {
    province_id: pid,
    active: true,
    band: 'medium',
    fillColor: baseColor,
    strokeColor: '#6d5b34',
    hatchPatternId: 'hatch-medium',
    metricText,
    badgeText: '灾荒待赈',
    valueWan: popCount !== undefined ? popCount / 10000 : null,
    isKnown: true,
    isStaleFact,
    factTurnNumber: primaryFact.turn_number,
    factAuthorId: primaryFact.author_character_id
  };
}

/**
 * Authoritative 1636 turn calendar helpers.
 * Turn 1 = 1636-01-01 (`1636年1月1日`), advancing 7 days per turn through Turn 4 (`1636年1月22日`).
 */
export function formatTurnCalendarIso(turnNumber: number): string {
  const safeTurn = Math.max(1, Math.floor(turnNumber));
  const startMs = Date.UTC(1636, 0, 1);
  const target = new Date(startMs + (safeTurn - 1) * 7 * 86_400_000);
  return target.toISOString().slice(0, 10);
}

export function formatTurnCalendarDate(turnNumber: number, isoOverride?: string): string {
  if (isoOverride && /^\d{4}-\d{2}-\d{2}$/.test(isoOverride)) {
    const [y, m, d] = isoOverride.split('-').map(Number);
    return `${y}年${m}月${d}日`;
  }
  const safeTurn = Math.max(1, Math.floor(turnNumber));
  const startMs = Date.UTC(1636, 0, 1);
  const target = new Date(startMs + (safeTurn - 1) * 7 * 86_400_000);
  const year = target.getUTCFullYear();
  const month = target.getUTCMonth() + 1;
  const day = target.getUTCDate();
  return `${year}年${month}月${day}日`;
}

export const formatWeekCalendarIso = formatTurnCalendarIso;
export const formatWeekCalendarDate = formatTurnCalendarDate;

export interface TurnHistoryOption {
  turn_number: number;
  date_iso: string;
  label: string;
  is_active: boolean;
}

export function buildAvailableHistoryTurnOptions(
  activeTurnNumber: number,
  availableTurns?: readonly number[]
): TurnHistoryOption[] {
  const turns =
    availableTurns && availableTurns.length > 0
      ? [...availableTurns].sort((a, b) => a - b)
      : Array.from({ length: Math.max(1, Math.min(4, Math.floor(activeTurnNumber))) }, (_, i) => i + 1);

  return turns.map((t) => {
    const dateIso = formatTurnCalendarIso(t);
    const dateLabel = formatTurnCalendarDate(t, dateIso);
    const isActive = t === activeTurnNumber;
    return {
      turn_number: t,
      date_iso: dateIso,
      label: isActive ? `${dateLabel} 当前` : `${dateLabel} 旧档`,
      is_active: isActive
    };
  });
}

export interface OutlinerProvinceParts {
  province_id: ProvinceId;
  title: string;
  officeTitle: string;
  governorName: string;
  reportStatusBadge: string;
  reportStatusTone: 'reported' | 'pending' | 'vacant';
  summaryText: string;
  planBadge: string | null;
  canalBadge: string | null;
}

export function formatOutlinerProvinceParts(
  provinceView: CourtProvinceView,
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>,
  viewedTurnNumber: number
): OutlinerProvinceParts {
  const characterId = provinceView.appointment?.character_id ?? null;
  const character = characterId ? characterById.get(characterId) : undefined;
  const governorName = character ? character.name : '悬缺';

  let reportStatusBadge = '本轮未奏';
  let reportStatusTone: 'reported' | 'pending' | 'vacant' = 'pending';
  if (!characterId) {
    reportStatusBadge = '巡抚悬缺';
    reportStatusTone = 'vacant';
  } else if (provinceView.current_officer_reported) {
    reportStatusBadge = '本轮已奏';
    reportStatusTone = 'reported';
  }

  const latestReport = provinceView.reports[provinceView.reports.length - 1];
  let summaryText = '尚无本省奏报记录';
  if (latestReport) {
    const authorName =
      characterById.get(latestReport.author_character_id)?.name ??
      latestReport.author_character_id;
    const isHistoricalReport = latestReport.turn_number < viewedTurnNumber;
    const prefix = isHistoricalReport
      ? `${formatTurnCalendarDate(latestReport.turn_number, latestReport.date)} ${authorName}：`
      : '';
    summaryText = `${prefix}${latestReport.body}`;
  }

  const positiveLockedPlans = provinceView.plans.filter(
    (p) => p.requested_amount > 0 && p.status === 'LOCKED'
  );
  const activeTurnPlans = provinceView.plans.filter((p) => p.turn_number === viewedTurnNumber);
  const planBadge =
    positiveLockedPlans.length > 0
      ? `待批方略 ${positiveLockedPlans.length} 项`
      : activeTurnPlans.length > 0
        ? `方略 ${activeTurnPlans.length} 项`
        : null;

  const canal = provinceView.project;
  const canalBadge = canal
    ? canal.completed_turn !== null
      ? `第${canal.completed_turn}轮修河竣工`
      : `修河已投 ${formatSilverAmountWan(canal.paid_silver)} / ${formatSilverAmountWan(canal.total_cost)}`
    : null;

  return {
    province_id: provinceView.province.province_id,
    title: provinceView.province.name,
    officeTitle: `${provinceView.province.name}巡抚`,
    governorName,
    reportStatusBadge,
    reportStatusTone,
    summaryText,
    planBadge,
    canalBadge
  };
}

export interface ProvinceOverviewNumbers {
  province_id: ProvinceId;
  name: string;
  active: boolean;
  baseColor: string;
  silverText: string;
  grainText: string;
  silverProvenance: string;
  grainProvenance: string;
  accessibleProvenance: string;
  isStale: boolean;
}

/**
 * Formats each province's known silver (`gross_silver`) and grain (`gross_grain`) numbers
 * for the right province overview (`十五地简况`).
 * - Uses real `CourtProvinceView.known` disclosure and provenance (never debug truth).
 * - Preserves explicit `0` as `银0.0万` / `粮0.0万` and missing/unknown values as `银—` / `粮—`
 *   with accessible provenance, never false zero or status headlines.
 */
export function formatProvinceOverviewNumbers(
  provinceView: CourtProvinceView,
  viewedTurnNumber: number,
  characterById?: ReadonlyMap<CharacterId, CharacterPublicView>
): ProvinceOverviewNumbers {
  const pid = provinceView.province.province_id;
  const baseColor = PROVINCE_BASE_COLOR_BY_ID[pid];

  if (!provinceView.province.active) {
    return {
      province_id: pid,
      name: provinceView.province.name,
      active: false,
      baseColor,
      silverText: '银—',
      grainText: '粮—',
      silverProvenance: '存银未奏报',
      grainProvenance: '存粮未奏报',
      accessibleProvenance: `${provinceView.province.name} 存银未奏报 存粮未奏报`,
      isStale: false
    };
  }

  const silverFact = provinceView.known.gross_silver;
  const grainFact = provinceView.known.gross_grain;

  const silverVal = getNumericFactValue(silverFact);
  const grainVal = getNumericFactValue(grainFact);

  const silverText =
    silverVal !== undefined ? `银${formatWanNumber(silverVal / 10000)}万` : '银—';
  const grainText =
    grainVal !== undefined ? `粮${formatWanNumber(grainVal / 10000)}万` : '粮—';

  const silverProv = formatFactProvenanceTag(silverFact, viewedTurnNumber, characterById);
  const grainProv = formatFactProvenanceTag(grainFact, viewedTurnNumber, characterById);

  const silverProvenance = silverProv.label || '存银未奏报';
  const grainProvenance = grainProv.label || '存粮未奏报';

  return {
    province_id: pid,
    name: provinceView.province.name,
    active: true,
    baseColor,
    silverText,
    grainText,
    silverProvenance,
    grainProvenance,
    accessibleProvenance: `${provinceView.province.name} 存银${silverVal !== undefined ? `${formatWanNumber(silverVal / 10000)}万两（${silverProvenance}）` : '未奏报'} 存粮${grainVal !== undefined ? `${formatWanNumber(grainVal / 10000)}万石（${grainProvenance}）` : '未奏报'}`,
    isStale: silverProv.isStale || grainProv.isStale
  };
}
