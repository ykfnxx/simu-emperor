'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import type {
  CourtProvinceView,
  GameplayDebugView,
  ProvinceId
} from '../../src/contracts/gameplay';
import terrainReliefAsset from '../assets/jiangshan/terrain_relief.webp';
import {
  computeProvinceLayerPresentation,
  computeSvgViewBox,
  formatGrainAmountWan,
  formatSilverAmountWan,
   getProvinceBaseColor,
  JIANGSHAN_BACKGROUND_MAP,
  MING_INTERIOR_BOUNDARY_PATH,
  MING_PROVINCE_GEOMETRIES,
  panCameraByScreenDelta,
  resolveProvinceIdFromProviderId,
  TERRAIN_RELIEF_RECT,
  zoomCameraAtScreenPoint,
  type LayerSeverityBand,
  type MapCamera,
  type MapLayerKind
} from '../map-data';

const terrainReliefUrl =
  typeof terrainReliefAsset === 'string'
    ? terrainReliefAsset
    : terrainReliefAsset.src;

export interface MapViewportProps {
  provinces: CourtProvinceView[];
  viewedTurnNumber: number;
  selectedProvinceId: ProvinceId | null;
  leftPanelOpen: boolean;
  activeLayer: MapLayerKind;
  camera: MapCamera;
  debugTruth: GameplayDebugView | null;
  onSelectProvince: (
    provinceId: ProvinceId,
    viewportWidth: number,
    viewportHeight: number
  ) => void;
  onClearSelection: () => void;
  onChangeCamera: React.Dispatch<React.SetStateAction<MapCamera>>;
}

function getBandBorderStroke(band: LayerSeverityBand, layer: MapLayerKind): string {
  if (band === 'frozen') {
    return '#6b604e';
  }
  if (band === 'unknown') {
    return '#6b604e';
  }
  if (layer === 'disaster') {
    if (band === 'high') return '#8f3628';
    if (band === 'medium') return '#946528';
    return '#586f54';
  }
  if (band === 'high') return '#586f54';
  if (band === 'medium') return '#946528';
  return '#8f3628';
}

function getBandStatusClass(band: LayerSeverityBand, layer: MapLayerKind): string {
  if (band === 'frozen') return 'frozen';
  if (band === 'unknown') return 'unknown';
  if (layer === 'disaster') {
    if (band === 'high') return 'urgent';
    if (band === 'medium') return 'mild';
    return 'stable';
  }
  if (band === 'high') return 'stable';
  if (band === 'medium') return 'mild';
  return 'urgent';
}

export const MapViewport: React.FC<MapViewportProps> = ({
  provinces,
  viewedTurnNumber,
  selectedProvinceId,
  leftPanelOpen,
  activeLayer,
  camera,
  debugTruth,
  onSelectProvince,
  onClearSelection,
  onChangeCamera
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [viewportSize, setViewportSize] = useState<{ width: number; height: number }>(() => ({
    width: typeof window !== 'undefined' ? window.innerWidth : 1440,
    height: typeof window !== 'undefined' ? window.innerHeight : 900
  }));
  const [dragging, setDragging] = useState(false);

  const cameraRef = useRef<MapCamera>(camera);
  cameraRef.current = camera;

  const activePointersRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  const pinchStateRef = useRef<{
    startDist: number;
    baseCam: MapCamera;
    rect: { left: number; top: number; width: number; height: number };
  } | null>(null);

  const dragRef = useRef<{
    active: boolean;
    pointerId: number;
    lastX: number;
    lastY: number;
    startX: number;
    startY: number;
    moved: boolean;
  }>({
    active: false,
    pointerId: -1,
    lastX: 0,
    lastY: 0,
    startX: 0,
    startY: 0,
    moved: false
  });

  useEffect(() => {
    const updateSize = () => {
      const rect = containerRef.current?.getBoundingClientRect();
      setViewportSize({
        width: rect?.width || window.innerWidth || 1440,
        height: rect?.height || window.innerHeight || 900
      });
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  const provinceById = useMemo(() => {
    const map = new Map<ProvinceId, CourtProvinceView>();
    for (const p of provinces) {
      map.set(p.province.province_id, p);
    }
    return map;
  }, [provinces]);

  const viewBoxString = useMemo(
    () => computeSvgViewBox(camera, viewportSize.width, viewportSize.height).viewBoxString,
    [camera, viewportSize.width, viewportSize.height]
  );

  const labelScale = useMemo(
    () => Number((1 / Math.sqrt(Math.max(0.65, Math.min(2.6, camera.zoom || 1)))).toFixed(3)),
    [camera.zoom]
  );
  const showSecondaryTowns = camera.zoom >= 0.92;

  const getContainerRect = () =>
    containerRef.current?.getBoundingClientRect() ?? {
      left: 0,
      top: 0,
      width: viewportSize.width,
      height: viewportSize.height
    };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === 'mouse' && e.button !== 0) {
      return;
    }

    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (activePointersRef.current.size === 1) {
      pinchStateRef.current = null;
      dragRef.current = {
        active: true,
        pointerId: e.pointerId,
        lastX: e.clientX,
        lastY: e.clientY,
        startX: e.clientX,
        startY: e.clientY,
        moved: false
      };
    } else if (activePointersRef.current.size === 2) {
      if (typeof e.currentTarget.setPointerCapture === 'function') {
        try {
          e.currentTarget.setPointerCapture(e.pointerId);
        } catch {
          // Ignore capture errors on synthetic pointers
        }
      }
      dragRef.current.active = false;
      dragRef.current.moved = true;
      setDragging(true);
      const pts = Array.from(activePointersRef.current.values());
      const startDist = Math.max(10, Math.hypot(pts[1]!.x - pts[0]!.x, pts[1]!.y - pts[0]!.y));
      pinchStateRef.current = {
        startDist,
        baseCam: cameraRef.current,
        rect: getContainerRect()
      };
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (activePointersRef.current.has(e.pointerId)) {
      activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    }

    if (activePointersRef.current.size === 2 && pinchStateRef.current) {
      const pts = Array.from(activePointersRef.current.values());
      const dist = Math.max(10, Math.hypot(pts[1]!.x - pts[0]!.x, pts[1]!.y - pts[0]!.y));
      const factor = dist / pinchStateRef.current.startDist;
      const midX = (pts[0]!.x + pts[1]!.x) * 0.5 - pinchStateRef.current.rect.left;
      const midY = (pts[0]!.y + pts[1]!.y) * 0.5 - pinchStateRef.current.rect.top;
      const nextCam = zoomCameraAtScreenPoint(
        pinchStateRef.current.baseCam,
        pinchStateRef.current.baseCam.zoom * factor,
        midX,
        midY,
        pinchStateRef.current.rect.width,
        pinchStateRef.current.rect.height
      );
      cameraRef.current = nextCam;
      onChangeCamera(nextCam);
      return;
    }

    if (!dragRef.current.active || activePointersRef.current.size !== 1) {
      return;
    }
    const totalDx = e.clientX - dragRef.current.startX;
    const totalDy = e.clientY - dragRef.current.startY;
    if (!dragRef.current.moved && Math.hypot(totalDx, totalDy) > 4) {
      dragRef.current.moved = true;
      setDragging(true);
      if (typeof e.currentTarget.setPointerCapture === 'function') {
        try {
          e.currentTarget.setPointerCapture(e.pointerId);
        } catch {
          // Ignore capture errors on synthetic pointers
        }
      }
    }
    if (dragRef.current.moved) {
      const stepDx = e.clientX - dragRef.current.lastX;
      const stepDy = e.clientY - dragRef.current.lastY;
      dragRef.current.lastX = e.clientX;
      dragRef.current.lastY = e.clientY;
      const nextCam = panCameraByScreenDelta(
        cameraRef.current,
        stepDx,
        stepDy,
        viewportSize.width,
        viewportSize.height
      );
      cameraRef.current = nextCam;
      onChangeCamera(nextCam);
    }
  };

  const endPointerDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    activePointersRef.current.delete(e.pointerId);
    if (
      typeof e.currentTarget.hasPointerCapture === 'function' &&
      e.currentTarget.hasPointerCapture(e.pointerId)
    ) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }

    if (activePointersRef.current.size < 2) {
      pinchStateRef.current = null;
    }
    if (activePointersRef.current.size === 1) {
      const [remId, remPt] = Array.from(activePointersRef.current.entries())[0]!;
      dragRef.current = {
        active: true,
        pointerId: remId,
        lastX: remPt.x,
        lastY: remPt.y,
        startX: remPt.x,
        startY: remPt.y,
        moved: true
      };
      return;
    }

    dragRef.current.active = false;
    setDragging(false);
  };

  const cancelPointerDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    activePointersRef.current.delete(e.pointerId);
    if (
      typeof e.currentTarget.hasPointerCapture === 'function' &&
      e.currentTarget.hasPointerCapture(e.pointerId)
    ) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    pinchStateRef.current = null;
    dragRef.current.active = false;
    dragRef.current.moved = true;
    setDragging(false);
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const rect = getContainerRect();
    const delta = e.deltaY < 0 ? 0.14 : -0.14;
    onChangeCamera((prev) =>
      zoomCameraAtScreenPoint(
        prev,
        prev.zoom + delta,
        e.clientX - rect.left,
        e.clientY - rect.top,
        rect.width,
        rect.height
      )
    );
  };

  const handleBackgroundClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (dragRef.current.moved) {
      return;
    }
    const target = e.target as Element;
    if (
      target.classList.contains('strategy-map-svg') ||
      target.classList.contains('map-ocean-bg') ||
      target.classList.contains('map-terrain-relief-img') ||
      target.classList.contains('map-province-shape')
    ) {
      onClearSelection();
    }
  };

  const triggerSelectByProviderId = (providerRegionId: number) => {
    const resolvedProvinceId = resolveProvinceIdFromProviderId(providerRegionId);
    if (!resolvedProvinceId) {
      return;
    }
    const vw =
      containerRef.current?.clientWidth ??
      (typeof window !== 'undefined' ? window.innerWidth : 1440);
    const vh =
      containerRef.current?.clientHeight ??
      (typeof window !== 'undefined' ? window.innerHeight : 900);
    onSelectProvince(resolvedProvinceId, vw, vh);
  };

  const selectedGeom = MING_PROVINCE_GEOMETRIES.find(
    (g) => g.province_id === selectedProvinceId
  );

  return (
    <div
      id="strategy-map"
      ref={containerRef}
      className={`map-viewport ${dragging ? 'is-dragging' : ''} ${leftPanelOpen ? 'is-drawer-open' : ''}`}
      data-testid="map-viewport"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerDrag}
      onPointerCancel={cancelPointerDrag}
      onLostPointerCapture={endPointerDrag}
      onWheel={handleWheel}
    >
      <div
        className="map-camera-stage"
        data-testid="map-camera-stage"
        data-pan-x={camera.panX}
        data-pan-y={camera.panY}
        data-zoom={camera.zoom}
        data-viewbox={viewBoxString}
      >
        <svg
          className="strategy-map-svg terrain-active"
          viewBox={viewBoxString}
          preserveAspectRatio="xMidYMid slice"
          role="img"
          aria-label="崇祯九年两京十三省江山舆图"
          onClick={handleBackgroundClick}
        >
          <defs>
            <linearGradient id="terrain-fade-h" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" className="terrain-edge-stop" />
              <stop offset="4.5%" className="terrain-edge-stop" stopOpacity="0" />
              <stop offset="94.5%" className="terrain-edge-stop" stopOpacity="0" />
              <stop offset="100%" className="terrain-edge-stop" />
            </linearGradient>

            <linearGradient id="terrain-fade-v" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" className="terrain-edge-stop" />
              <stop offset="4.5%" className="terrain-edge-stop" stopOpacity="0" />
              <stop offset="94.5%" className="terrain-edge-stop" stopOpacity="0" />
              <stop offset="100%" className="terrain-edge-stop" />
            </linearGradient>
          </defs>

          {/* 1. Base rice-paper sea & georeferenced Jiangshan topographic hillshade */}
          <rect
            id="ocean-bg"
            x="-2000"
            y="-2000"
            width="6000"
            height="6000"
            className="map-ocean-bg"
          />

          <g id="grp-terrain" className="map-terrain-group">
            <image
              id="terrain-relief-img"
              href={terrainReliefUrl}
              x={TERRAIN_RELIEF_RECT.x}
              y={TERRAIN_RELIEF_RECT.y}
              width={TERRAIN_RELIEF_RECT.width}
              height={TERRAIN_RELIEF_RECT.height}
              preserveAspectRatio="none"
              className="map-terrain-relief-img"
            />
            <rect
              x={TERRAIN_RELIEF_RECT.x}
              y={TERRAIN_RELIEF_RECT.y}
              width={TERRAIN_RELIEF_RECT.width}
              height={TERRAIN_RELIEF_RECT.height}
              fill="url(#terrain-fade-h)"
              pointerEvents="none"
            />
            <rect
              x={TERRAIN_RELIEF_RECT.x}
              y={TERRAIN_RELIEF_RECT.y}
              width={TERRAIN_RELIEF_RECT.width}
              height={TERRAIN_RELIEF_RECT.height}
              fill="url(#terrain-fade-v)"
              pointerEvents="none"
            />
          </g>

          {/* 2. Surrounding landmass context */}
          <g id="grp-surrounding-provinces" className="map-surrounding-group">
            <path d={JIANGSHAN_BACKGROUND_MAP.outerLandPath} className="map-province-shape" />
            <path
              d={JIANGSHAN_BACKGROUND_MAP.interiorBordersPath}
              className="map-province-boundary-interior"
            />
          </g>

          {/* 3. All 15 Ming Provincial Units (`s_ming_c` 1636–1643): 4-color topology preserved */}
          <g id="grp-ming-provinces" className="map-polities-group">
            {MING_PROVINCE_GEOMETRIES.map((geom) => {
              const resolvedId = resolveProvinceIdFromProviderId(geom.provider_region_id);
              if (!resolvedId) return null;
              const provinceView = provinceById.get(resolvedId);
              const pres = computeProvinceLayerPresentation(
                provinceView,
                activeLayer,
                viewedTurnNumber
              );
              const isSelected = selectedProvinceId === resolvedId;
              const statusClass = getBandStatusClass(pres.band, activeLayer);
              const baseColor = getProvinceBaseColor(resolvedId);
              const borderStroke = getBandBorderStroke(pres.band, activeLayer);

              return (
                <g
                  key={resolvedId}
                  className={`map-playable-province status-${statusClass} ${geom.active ? 'is-active-province' : 'is-frozen-province'} ${isSelected ? 'is-selected' : ''}`}
                  data-testid={`map-province-${resolvedId}`}
                  data-province-id={resolvedId}
                  data-provider-id={geom.provider_region_id}
                  data-active={geom.active ? 'true' : 'false'}
                  data-band={pres.band}
                  data-base-color={baseColor}
                  data-selected={isSelected ? 'true' : 'false'}
                  role="button"
                  tabIndex={0}
                  aria-label={`${geom.name} ${geom.active ? pres.metricText : '冻结疆域'}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (dragRef.current.moved) return;
                    triggerSelectByProviderId(geom.provider_region_id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      e.stopPropagation();
                      triggerSelectByProviderId(geom.provider_region_id);
                    }
                  }}
                >
                  <path
                    d={geom.outerPath}
                    fill={baseColor}
                    className={`map-polity-wash status-${statusClass} ${geom.active ? 'is-active' : 'is-frozen'}`}
                  />
                  <path d={geom.outerPath} className="map-polity-casing" />
                  <path
                    d={geom.outerPath}
                    fill="none"
                    stroke={borderStroke}
                    className={`map-polity-border ${geom.active ? 'is-active' : 'is-frozen'}`}
                  />
                </g>
              );
            })}

            {MING_INTERIOR_BOUNDARY_PATH && (
              <path
                d={MING_INTERIOR_BOUNDARY_PATH}
                className="map-polity-sub-boundary"
                pointerEvents="none"
              />
            )}
          </g>

          {/* 4. Hydrography Layer (1636 historical rivers & lakes) */}
          <g id="grp-rivers" className="map-hydro-group" pointerEvents="none">
            {JIANGSHAN_BACKGROUND_MAP.lakes.map((lk, idx) => (
              <path
                key={`lk-${idx}`}
                d={lk.path}
                className={lk.rank <= 1 ? 'hydro-lake rank-major' : 'hydro-lake'}
              />
            ))}
            {JIANGSHAN_BACKGROUND_MAP.rivers
              .filter((r) => r.rank <= 2)
              .map((r, idx) => (
                <path key={`rc-${idx}`} d={r.path} className="hydro-river-casing" />
              ))}
            {JIANGSHAN_BACKGROUND_MAP.rivers.map((riv, idx) => {
              const rankClass =
                riv.rank === 1
                  ? 'rank-trunk'
                  : riv.rank === 2
                    ? 'rank-major'
                    : riv.rank === 3
                      ? 'rank-med'
                      : 'rank-minor';
              return (
                <path key={`rv-${idx}`} d={riv.path} className={`hydro-river ${rankClass}`} />
              );
            })}
            {JIANGSHAN_BACKGROUND_MAP.hydroLabels
              .filter((lb) => lb.kind === 'trunk')
              .map((wc, idx) => (
                <text
                  key={`hl-${idx}`}
                  transform={`translate(${wc.x},${wc.y}) scale(${labelScale}) rotate(${wc.rot})`}
                  className="hydro-label is-trunk"
                >
                  {wc.zh}
                </text>
              ))}
          </g>

          {/* 5. Selected Province Border Highlight */}
          {selectedGeom && (
            <g
              id="grp-selected-outline"
              className="map-selected-outline-group"
              pointerEvents="none"
            >
              <path d={selectedGeom.outerPath} className="map-selected-halo" />
              <path d={selectedGeom.outerPath} className="map-selected-border" />
            </g>
          )}

          {/* 6. Province Seats, Prefecture Markers & Titles across all 15 Ming Provinces */}
          <g id="grp-captions" className="map-captions-group">
            {MING_PROVINCE_GEOMETRIES.map((geom) => {
              const resolvedId = resolveProvinceIdFromProviderId(geom.provider_region_id);
              if (!resolvedId) return null;
              const provinceView = provinceById.get(resolvedId);
              const pres = computeProvinceLayerPresentation(
                provinceView,
                activeLayer,
                viewedTurnNumber
              );
              const isSelected = selectedProvinceId === resolvedId;
              const statusClass = getBandStatusClass(pres.band, activeLayer);
              const debugHidden =
                geom.active && debugTruth
                  ? debugTruth.provinces.find((dp) => dp.province_id === resolvedId)
                  : undefined;

              return (
                <g
                  key={`annot-${resolvedId}`}
                  className={`map-state-annotations ${geom.active ? 'is-active' : 'is-frozen'} ${isSelected ? 'is-selected' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (dragRef.current.moved) return;
                    triggerSelectByProviderId(geom.provider_region_id);
                  }}
                >
                  {geom.active &&
                    showSecondaryTowns &&
                    geom.towns
                      .filter((t) => !t.isCapital)
                      .map((town) => (
                        <g
                          key={town.name}
                          transform={`translate(${town.x},${town.y}) scale(${labelScale})`}
                          className="map-town-marker"
                        >
                          <circle cx="0" cy="0" r="0.82" className="map-town-dot" />
                          <text x="1.8" y="0.25" className="map-town-label">
                            {town.name}
                          </text>
                        </g>
                      ))}

                  {(geom.active || isSelected || camera.zoom >= 1.05) && (
                    <g
                      transform={`translate(${geom.capitalX},${geom.capitalY}) scale(${labelScale})`}
                      className={`map-seat-marker ${isSelected ? 'is-selected' : ''}`}
                    >
                      <circle
                        cx="0"
                        cy="0"
                        r={isSelected ? '1.85' : geom.active ? '1.35' : '1.05'}
                        className="map-seat-outer-ring"
                      />
                      {isSelected && (
                        <circle cx="0" cy="0" r="0.75" className="map-seat-inner-dot" />
                      )}
                      <text x="2.8" y="0.3" className="map-seat-label">
                        {geom.seat_name}
                      </text>
                    </g>
                  )}

                  <g
                    transform={`translate(${geom.labelCenterX},${geom.labelCenterY}) scale(${labelScale})`}
                    className="map-state-title-group"
                  >
                    <text
                      x="0"
                      y="0"
                      textAnchor="middle"
                      className={`map-state-title status-${statusClass} ${geom.active ? 'is-active-title' : 'is-frozen-title'} ${isSelected ? 'is-selected' : ''}`}
                    >
                      {geom.name}
                    </text>

                    <text
                      x="0"
                      y={geom.active ? '6.2' : '4.8'}
                      textAnchor="middle"
                      className={`map-state-sub-caption is-visible ${geom.active ? '' : 'is-frozen-sub'}`}
                      data-testid={`map-badge-sub-${resolvedId}`}
                    >
                      {geom.active ? pres.metricText : '冻结'}
                    </text>

                    {debugHidden && (
                      <text
                        x="0"
                        y="11.8"
                        textAnchor="middle"
                        className="map-state-debug-caption"
                        data-testid={`map-debug-truth-${resolvedId}`}
                      >
                        真值 银{formatSilverAmountWan(debugHidden.facts.gross_silver)} 粮
                        {formatGrainAmountWan(debugHidden.facts.gross_grain)}
                      </text>
                    )}
                  </g>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    </div>
  );
};
