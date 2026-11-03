import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  formatWan,
  type CourtStateView,
  type DebugTruthResponse,
  type MapReportSeverity,
  type StateId,
} from '../../src/contracts/index.ts';
import terrainReliefUrl from '../assets/jiangshan/terrain_relief.webp';
import {
  BACKGROUND_REGION_GEOMETRIES,
  computeStateLayerPresentation,
  computeSvgCameraViewBox,
  getBackgroundGeographyLayer,
  getLayerLegendEntries,
  getProjectedHydroLayer,
  INITIAL_MAP_CAMERA,
  PLAYABLE_PROVINCE_GEOMETRIES,
  TERRAIN_RELIEF_RECT,
  WATER_CAPTIONS,
  zoomCameraAtClientPoint,
  type MapCameraState,
  type MapLayerKind,
} from '../map-data.ts';

export interface MapViewportProps {
  states: CourtStateView[];
  selectedStateId: StateId | null;
  drawerOpen: boolean;
  activeLayer: MapLayerKind;
  camera: MapCameraState;
  debugTruth: DebugTruthResponse | null;
  onSelectState: (stateId: StateId, viewportWidth: number, viewportHeight: number) => void;
  onClearSelection: () => void;
  onChangeLayer: (layer: MapLayerKind) => void;
  onChangeCamera: React.Dispatch<React.SetStateAction<MapCameraState>>;
}

function getPolityWashFill(severity: Exclude<MapReportSeverity, 'background'>): string {
  switch (severity) {
    case 'urgent':
      return '#B54434';
    case 'mild':
      return '#C88A3B';
    case 'stable':
      return '#7A9A76';
    case 'unknown':
      return '#9A9488';
  }
}

function getPolityBorderColor(
  severity: Exclude<MapReportSeverity, 'background'>,
  isSelected: boolean,
): string {
  if (isSelected) {
    return '#8C2D22';
  }
  switch (severity) {
    case 'urgent':
      return '#8F3628';
    case 'mild':
      return '#946528';
    case 'stable':
      return '#586F54';
    case 'unknown':
      return '#7A7067';
  }
}

export const MapViewport: React.FC<MapViewportProps> = ({
  states,
  selectedStateId,
  drawerOpen,
  activeLayer,
  camera,
  debugTruth,
  onSelectState,
  onClearSelection,
  onChangeLayer,
  onChangeCamera,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [viewportSize, setViewportSize] = useState<{ width: number; height: number }>(() => ({
    width: typeof window !== 'undefined' ? window.innerWidth : 1440,
    height: typeof window !== 'undefined' ? window.innerHeight : 900,
  }));
  const [dragging, setDragging] = useState(false);

  const cameraRef = useRef<MapCameraState>(camera);
  cameraRef.current = camera;

  const activePointersRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  const pinchStateRef = useRef<{
    startDist: number;
    baseCam: MapCameraState;
    rect: { left: number; top: number; width: number; height: number };
  } | null>(null);

  const dragRef = useRef<{
    active: boolean;
    pointerId: number;
    startX: number;
    startY: number;
    basePanX: number;
    basePanY: number;
    moved: boolean;
  }>({
    active: false,
    pointerId: -1,
    startX: 0,
    startY: 0,
    basePanX: 0,
    basePanY: 0,
    moved: false,
  });

  useEffect(() => {
    const updateSize = () => {
      const rect = containerRef.current?.getBoundingClientRect();
      setViewportSize({
        width: rect?.width || window.innerWidth || 1440,
        height: rect?.height || window.innerHeight || 900,
      });
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Memoize static cartographic layers built from jiangshan-map outlines & hydrography
  const backgroundGeo = useMemo(() => getBackgroundGeographyLayer(), []);
  const hydroLayer = useMemo(() => getProjectedHydroLayer(), []);
  const legendEntries = useMemo(() => getLayerLegendEntries(activeLayer), [activeLayer]);

  const viewBoxString = useMemo(
    () => computeSvgCameraViewBox(camera, viewportSize.width, viewportSize.height),
    [camera, viewportSize.width, viewportSize.height],
  );

  // Inverse square-root label scale so captions and town labels stay crisp across zoom levels
  const labelScale = useMemo(
    () => Number((1 / Math.sqrt(Math.max(0.65, Math.min(2.6, camera.zoom || 1)))).toFixed(3)),
    [camera.zoom],
  );
  const showSecondaryTowns = camera.zoom >= 0.8;

  const stateById = (stateId: StateId): CourtStateView | undefined =>
    states.find((s) => s.state_id === stateId);

  const getContainerRect = () =>
    containerRef.current?.getBoundingClientRect() ?? {
      left: 0,
      top: 0,
      width: viewportSize.width,
      height: viewportSize.height,
    };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('.map-bottom-right-controls')) {
      return;
    }
    if (e.pointerType === 'mouse' && e.button !== 0) {
      return;
    }

    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (typeof e.currentTarget.setPointerCapture === 'function') {
      e.currentTarget.setPointerCapture(e.pointerId);
    }

    if (activePointersRef.current.size === 1) {
      pinchStateRef.current = null;
      dragRef.current = {
        active: true,
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        basePanX: cameraRef.current.panX,
        basePanY: cameraRef.current.panY,
        moved: false,
      };
    } else if (activePointersRef.current.size === 2) {
      dragRef.current.active = false;
      dragRef.current.moved = true;
      setDragging(true);
      const pts = Array.from(activePointersRef.current.values());
      const startDist = Math.max(10, Math.hypot(pts[1]!.x - pts[0]!.x, pts[1]!.y - pts[0]!.y));
      pinchStateRef.current = {
        startDist,
        baseCam: cameraRef.current,
        rect: getContainerRect(),
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
      const midX = (pts[0]!.x + pts[1]!.x) * 0.5;
      const midY = (pts[0]!.y + pts[1]!.y) * 0.5;
      const nextCam = zoomCameraAtClientPoint(
        pinchStateRef.current.baseCam,
        pinchStateRef.current.baseCam.zoom * factor,
        midX,
        midY,
        pinchStateRef.current.rect,
      );
      cameraRef.current = nextCam;
      onChangeCamera(nextCam);
      return;
    }

    if (!dragRef.current.active || activePointersRef.current.size !== 1) {
      return;
    }
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    if (!dragRef.current.moved && Math.hypot(dx, dy) > 4) {
      dragRef.current.moved = true;
      setDragging(true);
    }
    if (dragRef.current.moved) {
      const maxPanX = Math.max(680, Math.round(viewportSize.width * cameraRef.current.zoom * 0.9));
      const maxPanY = Math.max(480, Math.round(viewportSize.height * cameraRef.current.zoom * 0.9));
      const nextPanX = Math.max(
        -maxPanX,
        Math.min(maxPanX, Math.round(dragRef.current.basePanX + dx)),
      );
      const nextPanY = Math.max(
        -maxPanY,
        Math.min(maxPanY, Math.round(dragRef.current.basePanY + dy)),
      );
      const nextCam = {
        ...cameraRef.current,
        panX: nextPanX,
        panY: nextPanY,
      };
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
        startX: remPt.x,
        startY: remPt.y,
        basePanX: cameraRef.current.panX,
        basePanY: cameraRef.current.panY,
        moved: true,
      };
      return;
    }

    dragRef.current.active = false;
    setDragging(false);
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('.map-bottom-right-controls')) {
      return;
    }
    const rect = containerRef.current?.getBoundingClientRect() ?? {
      left: 0,
      top: 0,
      width: viewportSize.width,
      height: viewportSize.height,
    };
    const delta = e.deltaY < 0 ? 0.14 : -0.14;
    onChangeCamera((prev) =>
      zoomCameraAtClientPoint(prev, prev.zoom + delta, e.clientX, e.clientY, rect),
    );
  };

  const handleStepZoom = (delta: number) => {
    const rect = containerRef.current?.getBoundingClientRect() ?? {
      left: 0,
      top: 0,
      width: viewportSize.width,
      height: viewportSize.height,
    };
    const centerClientX = rect.left + rect.width * 0.54;
    const centerClientY = rect.top + rect.height * 0.5;
    onChangeCamera((prev) =>
      zoomCameraAtClientPoint(prev, prev.zoom + delta, centerClientX, centerClientY, rect),
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

  const selectedGeom = PLAYABLE_PROVINCE_GEOMETRIES.find((p) => p.state_id === selectedStateId);

  return (
    <div
      ref={containerRef}
      className={`map-viewport ${dragging ? 'is-dragging' : ''} ${drawerOpen ? 'is-drawer-open' : ''}`}
      data-testid="map-viewport"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerDrag}
      onPointerCancel={endPointerDrag}
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
          aria-label="江山舆图 · 三州疆域"
          onClick={handleBackgroundClick}
        >
          <defs>
            <filter id="label-halo" x="-20%" y="-20%" width="140%" height="140%">
              <feMorphology operator="dilate" radius="1.2" in="SourceAlpha" result="dilated" />
              <feFlood floodColor="#FAF7F2" floodOpacity="0.92" result="bg" />
              <feComposite in="bg" in2="dilated" operator="in" result="outline" />
              <feMerge>
                <feMergeNode in="outline" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

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

            {/* Diagonal hatch pattern for UNKNOWN / unreported states */}
            <pattern
              id="unknown-hatch-pattern"
              width="6"
              height="6"
              patternTransform="rotate(45 0 0)"
              patternUnits="userSpaceOnUse"
            >
              <rect width="6" height="6" fill="rgba(222, 216, 204, 0.32)" />
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="6"
                stroke="rgba(122, 112, 103, 0.45)"
                strokeWidth="1.5"
              />
            </pattern>
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

          {/* 2. Surrounding neutral landmass & deduplicated regional boundaries from jiangshan-map */}
          <g id="grp-surrounding-provinces" className="map-surrounding-group">
            {backgroundGeo.landmassShapes.map((d, idx) => (
              <path key={idx} d={d} className="map-province-shape" />
            ))}
            {backgroundGeo.combinedBoundaries ? (
              <path d={backgroundGeo.combinedBoundaries} className="map-province-boundary-casing" />
            ) : null}
            {backgroundGeo.interiorBoundaries ? (
              <path
                d={backgroundGeo.interiorBoundaries}
                className="map-province-boundary-interior"
              />
            ) : null}
            {backgroundGeo.outerBoundaries ? (
              <path d={backgroundGeo.outerBoundaries} className="map-province-boundary-outer" />
            ) : null}
          </g>

          {/* 3. Playable State Territories (low-opacity watercolor washes + sub-boundaries) */}
          <g id="grp-playable-polities" className="map-polities-group">
            {PLAYABLE_PROVINCE_GEOMETRIES.map((geom) => {
              const stateData = stateById(geom.state_id);
              const pres = stateData
                ? computeStateLayerPresentation(stateData, activeLayer)
                : { severityKey: 'unknown' as const, badgeSubtitle: '本周未奏报（未知）' };
              const isSelected = selectedStateId === geom.state_id;
              const washFill = getPolityWashFill(pres.severityKey);
              const borderStroke = getPolityBorderColor(pres.severityKey, false);

              return (
                <g
                  key={geom.state_id}
                  className={`map-playable-province status-${pres.severityKey} ${isSelected ? 'is-selected' : ''}`}
                  data-testid={`map-province-${geom.state_id}`}
                  data-severity={pres.severityKey}
                  data-selected={isSelected ? 'true' : 'false'}
                  role="button"
                  tabIndex={0}
                  aria-label={`${geom.state_name}（${pres.badgeSubtitle}）`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (dragRef.current.moved) return;
                    const vw =
                      containerRef.current?.clientWidth ??
                      (typeof window !== 'undefined' ? window.innerWidth : 1280);
                    const vh =
                      containerRef.current?.clientHeight ??
                      (typeof window !== 'undefined' ? window.innerHeight : 800);
                    onSelectState(geom.state_id, vw, vh);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      const vw =
                        containerRef.current?.clientWidth ??
                        (typeof window !== 'undefined' ? window.innerWidth : 1280);
                      const vh =
                        containerRef.current?.clientHeight ??
                        (typeof window !== 'undefined' ? window.innerHeight : 800);
                      onSelectState(geom.state_id, vw, vh);
                    }
                  }}
                >
                  {/* Watercolor wash over topographic hillshade */}
                  <path
                    d={geom.d}
                    fill={washFill}
                    className={`map-polity-wash status-${pres.severityKey}`}
                  />

                  {/* Diagonal hatch overlay when report is UNKNOWN */}
                  {pres.severityKey === 'unknown' && (
                    <path
                      d={geom.d}
                      fill="url(#unknown-hatch-pattern)"
                      className="map-polity-unknown-hatch"
                    />
                  )}

                  {/* Subtle internal prefecture/jun dashed division lines */}
                  {geom.subBoundaryPath && (
                    <path d={geom.subBoundaryPath} className="map-polity-sub-boundary" />
                  )}

                  {/* Outer light paper casing + state boundary stroke */}
                  <path d={geom.d} className="map-polity-casing" />
                  <path
                    d={geom.d}
                    fill="none"
                    stroke={borderStroke}
                    className="map-polity-border"
                  />
                </g>
              );
            })}
          </g>

          {/* 4. Hydrography Layer (lakes & ranked rivers rendered over state washes, as in jiangshan-map) */}
          <g id="grp-rivers" className="map-hydro-group" pointerEvents="none">
            {hydroLayer.lakes.map((lk, idx) => (
              <path
                key={`lk-${idx}`}
                d={lk.d}
                className={lk.major ? 'hydro-lake rank-major' : 'hydro-lake'}
              />
            ))}
            {hydroLayer.trunkCasingPaths.map((d, idx) => (
              <path key={`rc-${idx}`} d={d} className="hydro-river-casing" />
            ))}
            {hydroLayer.rivers.map((riv, idx) => (
              <path key={`rv-${idx}`} d={riv.d} className={`hydro-river ${riv.rankClass}`} />
            ))}
            {WATER_CAPTIONS.map((wc) => (
              <text
                key={wc.id}
                transform={`translate(${wc.x},${wc.y}) scale(${labelScale}) rotate(${wc.rot})`}
                className="hydro-label is-trunk"
              >
                {wc.name}
              </text>
            ))}
          </g>

          {/* 5. Selected State Crisp Cinnabar Highlight Outline */}
          {selectedGeom && (
            <g
              id="grp-selected-outline"
              className="map-selected-outline-group"
              pointerEvents="none"
            >
              <path d={selectedGeom.d} className="map-selected-halo" />
              <path d={selectedGeom.d} className="map-selected-border" />
            </g>
          )}

          {/* 6. Non-Playable Surrounding Regional Captions, Town Markers, Prefecture Seats & State Titles */}
          <g id="grp-captions" className="map-captions-group">
            {BACKGROUND_REGION_GEOMETRIES.map((bg) => (
              <g
                key={bg.province_id}
                className="map-bg-region-group"
                data-testid={`map-background-${bg.province_id}`}
                aria-disabled="true"
                onClick={(e) => {
                  // Clicking surrounding geographic background never switches active state
                  e.stopPropagation();
                }}
              >
                <title>{`${bg.region_name} · ${bg.map_status_label}`}</title>
                <rect
                  x={bg.labelPos.x - 28}
                  y={bg.labelPos.y - 9}
                  width="56"
                  height="18"
                  fill="transparent"
                />
                <text
                  transform={`translate(${bg.labelPos.x},${bg.labelPos.y}) scale(${labelScale})`}
                  className={`map-regional-caption ${bg.province_id === 'bg_south' || bg.display_caption === '东海湾' ? 'kind-sea' : 'kind-land'}`}
                >
                  {bg.display_caption}
                </text>
              </g>
            ))}

            {PLAYABLE_PROVINCE_GEOMETRIES.map((geom) => {
              const stateData = stateById(geom.state_id);
              const pres = stateData
                ? computeStateLayerPresentation(stateData, activeLayer)
                : { severityKey: 'unknown' as const, badgeSubtitle: '本周未奏报（未知）' };
              const isSelected = selectedStateId === geom.state_id;
              const debugState = debugTruth?.states.find((s) => s.state_id === geom.state_id);
              const showBadgeSub =
                activeLayer !== 'disaster' || pres.severityKey === 'unknown';

              return (
                <g
                  key={`annot-${geom.state_id}`}
                  className={`map-state-annotations ${isSelected ? 'is-selected' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (dragRef.current.moved) return;
                    const vw =
                      containerRef.current?.clientWidth ??
                      (typeof window !== 'undefined' ? window.innerWidth : 1280);
                    const vh =
                      containerRef.current?.clientHeight ??
                      (typeof window !== 'undefined' ? window.innerHeight : 800);
                    onSelectState(geom.state_id, vw, vh);
                  }}
                >
                  {/* Secondary sub-towns */}
                  {showSecondaryTowns &&
                    geom.towns.map((town) => (
                      <g
                        key={town.name}
                        transform={`translate(${town.x},${town.y}) scale(${labelScale})`}
                        className="map-town-marker"
                      >
                        <circle cx="0" cy="0" r="0.85" className="map-town-dot" />
                        <text x="1.9" y="0.25" className="map-town-label">
                          {town.name}
                        </text>
                      </g>
                    ))}

                  {/* Prefecture Seat Marker (○ / ◎) */}
                  <g
                    transform={`translate(${geom.seat.x - 9},${geom.seat.y}) scale(${labelScale})`}
                    className={`map-seat-marker ${isSelected ? 'is-selected' : ''}`}
                  >
                    <circle
                      cx="0"
                      cy="0"
                      r={isSelected ? '1.9' : '1.35'}
                      className="map-seat-outer-ring"
                    />
                    {isSelected && <circle cx="0" cy="0" r="0.8" className="map-seat-inner-dot" />}
                    <text x="3.1" y="0.3" className="map-seat-label">
                      {geom.seat.name}
                    </text>
                  </g>

                  {/* Primary Classical Serif State Title */}
                  <g
                    transform={`translate(${geom.center.x},${geom.center.y - 2}) scale(${labelScale})`}
                    className="map-state-title-group"
                  >
                    <text
                      x="0"
                      y="0"
                      textAnchor="middle"
                      className={`map-state-title status-${pres.severityKey} ${isSelected ? 'is-selected' : ''}`}
                    >
                      {geom.state_name}
                    </text>

                    <text
                      x="0"
                      y="6.4"
                      textAnchor="middle"
                      className={`map-state-sub-caption ${showBadgeSub ? 'is-visible' : 'is-compact'}`}
                      data-testid={`map-badge-sub-${geom.state_id}`}
                    >
                      {pres.badgeSubtitle}
                    </text>

                    {debugState && (
                      <text
                        x="0"
                        y="12.5"
                        textAnchor="middle"
                        className="map-state-debug-caption"
                        data-testid={`map-debug-truth-${geom.state_id}`}
                      >
                        [真值 粮{formatWan(debugState.truth.disposable_grain, '万石')}/银
                        {formatWan(debugState.truth.disposable_silver, '万两')}]
                      </text>
                    )}
                  </g>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* Lower-Right Compact Map Controls & Honest 5-State Legend (Matches simple-ui-preview-v1.png) */}
      <div className="map-bottom-right-controls" data-testid="map-controls-dock">
        <div className="map-control-row">
          <div
            className="map-layer-pill-group"
            role="group"
            aria-label="舆图图层切换"
            data-testid="map-layer-switcher"
          >
            <button
              type="button"
              className={`map-layer-pill ${activeLayer === 'disaster' ? 'active' : ''}`}
              aria-pressed={activeLayer === 'disaster'}
              data-testid="layer-btn-disaster"
              onClick={() => onChangeLayer('disaster')}
            >
              灾情
            </button>
            <button
              type="button"
              className={`map-layer-pill ${activeLayer === 'grain' ? 'active' : ''}`}
              aria-pressed={activeLayer === 'grain'}
              data-testid="layer-btn-grain"
              onClick={() => onChangeLayer('grain')}
            >
              存粮
            </button>
            <button
              type="button"
              className={`map-layer-pill ${activeLayer === 'silver' ? 'active' : ''}`}
              aria-pressed={activeLayer === 'silver'}
              data-testid="layer-btn-silver"
              onClick={() => onChangeLayer('silver')}
            >
              存银
            </button>
          </div>

          <div className="map-zoom-pill-group" role="group" aria-label="舆图视野控制">
            <button
              type="button"
              className="map-zoom-btn"
              data-testid="map-zoom-in-btn"
              title="放大地图"
              aria-label="放大地图"
              onClick={() => handleStepZoom(0.18)}
            >
              +
            </button>
            <button
              type="button"
              className="map-zoom-btn"
              data-testid="map-zoom-out-btn"
              title="缩小地图"
              aria-label="缩小地图"
              onClick={() => handleStepZoom(-0.18)}
            >
              −
            </button>
            <button
              type="button"
              className="map-reset-btn"
              data-testid="map-reset-camera-btn"
              title="复位视图"
              onClick={() => onChangeCamera(INITIAL_MAP_CAMERA)}
            >
              复位视图
            </button>
          </div>
        </div>

        <div className="map-legend-card" data-testid="map-layer-legend" aria-label="舆图图例">
          {legendEntries.map((entry) => (
            <span
              key={entry.key}
              className="legend-item"
              data-testid={`legend-item-${entry.key}`}
              title={entry.detailLabel}
            >
              <i className={`legend-swatch swatch-${entry.key}`} />
              <span>{entry.shortLabel}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
