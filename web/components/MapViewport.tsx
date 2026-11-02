import React, { useEffect, useRef, useState } from 'react';
import {
  formatWan,
  type CourtStateView,
  type DebugTruthResponse,
  type MapReportSeverity,
  type StateId,
} from '../../src/contracts/index.ts';
import {
  BACKGROUND_REGION_GEOMETRIES,
  computeStateLayerPresentation,
  getLayerLegendEntries,
  getStateScreenCenterX,
  INITIAL_MAP_CAMERA,
  MAP_RIVER_PATHS,
  MAP_VIEWBOX_HEIGHT,
  MAP_VIEWBOX_WIDTH,
  PLAYABLE_PROVINCE_GEOMETRIES,
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
  onSelectState: (stateId: StateId, viewportWidth: number) => void;
  onClearSelection: () => void;
  onChangeLayer: (layer: MapLayerKind) => void;
  onChangeCamera: (next: MapCameraState) => void;
}

const SEVERITY_FILL_MAP: Record<MapReportSeverity, string> = {
  urgent: '#b24338',
  mild: '#e69d56',
  stable: '#b8ca8d',
  unknown: 'url(#unknown-hatch-pattern)',
  background: '#ded5c3',
};

const SEVERITY_STROKE_MAP: Record<MapReportSeverity, string> = {
  urgent: '#6b1d15',
  mild: '#8a521b',
  stable: '#4f642c',
  unknown: '#4a433c',
  background: '#8d8272',
};

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
  const [viewportWidth, setViewportWidth] = useState<number>(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1280,
  );
  const [hoveredStateId, setHoveredStateId] = useState<StateId | null>(null);
  const [hoverPos, setHoverPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const dragRef = useRef<{
    active: boolean;
    moved: boolean;
    startX: number;
    startY: number;
    originPanX: number;
    originPanY: number;
  }>({
    active: false,
    moved: false,
    startX: 0,
    startY: 0,
    originPanX: 0,
    originPanY: 0,
  });

  const wheelStateRef = useRef<{
    camera: MapCameraState;
    viewportWidth: number;
    onChangeCamera: (next: MapCameraState) => void;
  }>({
    camera,
    viewportWidth,
    onChangeCamera,
  });
  wheelStateRef.current = {
    camera,
    viewportWidth,
    onChangeCamera,
  };

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setViewportWidth(containerRef.current.clientWidth || window.innerWidth);
      } else {
        setViewportWidth(window.innerWidth);
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      observer = new ResizeObserver(() => updateSize());
      observer.observe(containerRef.current);
    }
    return () => {
      window.removeEventListener('resize', updateSize);
      observer?.disconnect();
    };
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleNativeWheel = (e: WheelEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest('.map-layer-capsule') || target?.closest('.map-camera-controls')) {
        return;
      }
      e.preventDefault();
      const {
        camera: currCam,
        viewportWidth: currVw,
        onChangeCamera: emitCamera,
      } = wheelStateRef.current;
      const rect = el.getBoundingClientRect();
      const cursorX = rect ? e.clientX - rect.left : currVw / 2;
      const cursorY = rect ? e.clientY - rect.top : 354;

      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
      const nextZoom = Math.min(2.4, Math.max(0.65, Number((currCam.zoom * zoomFactor).toFixed(3))));
      if (nextZoom === currCam.zoom) return;

      const scaleRatio = nextZoom / currCam.zoom;
      const nextPanX = Math.round((cursorX - (cursorX - currCam.panX) * scaleRatio) * 100) / 100;
      const nextPanY = Math.round((cursorY - (cursorY - currCam.panY) * scaleRatio) * 100) / 100;

      emitCamera({
        panX: nextPanX,
        panY: nextPanY,
        zoom: nextZoom,
      });
    };

    el.addEventListener('wheel', handleNativeWheel, { passive: false });
    return () => {
      el.removeEventListener('wheel', handleNativeWheel);
    };
  }, []);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement;
    if (target.closest('.map-layer-capsule') || target.closest('.map-camera-controls')) {
      return;
    }
    dragRef.current = {
      active: true,
      moved: false,
      startX: e.clientX,
      startY: e.clientY,
      originPanX: camera.panX,
      originPanY: camera.panY,
    };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setHoverPos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
    if (!dragRef.current.active) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
      dragRef.current.moved = true;
      onChangeCamera({
        panX: Math.round(dragRef.current.originPanX + dx),
        panY: Math.round(dragRef.current.originPanY + dy),
        zoom: camera.zoom,
      });
    }
  };

  const handlePointerUp = () => {
    dragRef.current.active = false;
    setTimeout(() => {
      dragRef.current.moved = false;
    }, 0);
  };

  const adjustZoom = (delta: number) => {
    const nextZoom = Math.min(2.4, Math.max(0.65, Number((camera.zoom + delta).toFixed(2))));
    if (nextZoom === camera.zoom) return;
    const centerX = viewportWidth * (drawerOpen ? 0.375 : 0.5);
    const centerY = 354;
    const scaleRatio = nextZoom / camera.zoom;
    onChangeCamera({
      panX: Math.round((centerX - (centerX - camera.panX) * scaleRatio) * 100) / 100,
      panY: Math.round((centerY - (centerY - camera.panY) * scaleRatio) * 100) / 100,
      zoom: nextZoom,
    });
  };

  const legendEntries = getLayerLegendEntries(activeLayer);
  const hoveredState = hoveredStateId
    ? states.find((s) => s.state_id === hoveredStateId) ?? null
    : null;
  const hoveredPresentation = hoveredState
    ? computeStateLayerPresentation(hoveredState, activeLayer)
    : null;

  const selectedScreenX =
    selectedStateId !== null
      ? Math.round(getStateScreenCenterX(selectedStateId, viewportWidth, camera))
      : null;
  const selectedScreenRatio =
    selectedScreenX !== null && viewportWidth > 0
      ? Number((selectedScreenX / viewportWidth).toFixed(3))
      : null;

  return (
    <div
      ref={containerRef}
      className="map-viewport"
      data-testid="map-viewport"
      data-active-layer={activeLayer}
      data-selected-state={selectedStateId ?? ''}
      data-drawer-open={drawerOpen ? 'true' : 'false'}
      data-camera-pan-x={camera.panX}
      data-camera-pan-y={camera.panY}
      data-camera-zoom={camera.zoom}
      data-selected-screen-x={selectedScreenX ?? ''}
      data-selected-screen-ratio={selectedScreenRatio ?? ''}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
    >
      <div
        className="map-camera-stage"
        style={{
          transformOrigin: '0 0',
          transform: `translate3d(${camera.panX}px, ${camera.panY}px, 0) scale(${camera.zoom})`,
        }}
      >
        <svg
          className="strategy-map-svg"
          viewBox={`0 0 ${MAP_VIEWBOX_WIDTH} ${MAP_VIEWBOX_HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="江山州郡奏报舆图"
        >
          <defs>
            {/* Diagonal hatch pattern for playable states with UNKNOWN report status */}
            <pattern
              id="unknown-hatch-pattern"
              width="14"
              height="14"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="14" height="14" fill="#847c72" />
              <line x1="0" y1="0" x2="0" y2="14" stroke="#575048" strokeWidth="5" />
            </pattern>

            {/* Warm golden halo for the currently selected playable state */}
            <filter id="selected-state-glow" x="-15%" y="-15%" width="130%" height="130%">
              <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#f7c86a" floodOpacity="0.95" />
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#4b2c0d" floodOpacity="0.45" />
            </filter>

            <linearGradient id="parchment-bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#e5dcc8" />
              <stop offset="50%" stopColor="#ded4bf" />
              <stop offset="100%" stopColor="#d4c7ae" />
            </linearGradient>

            <linearGradient id="mountain-ink-grad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#6e685f" stopOpacity="0.58" />
              <stop offset="65%" stopColor="#9c9384" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#ded4bf" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          {/* Base parchment paper background */}
          <rect
            x="0"
            y="0"
            width={MAP_VIEWBOX_WIDTH}
            height={MAP_VIEWBOX_HEIGHT}
            fill="url(#parchment-bg-grad)"
            onClick={() => {
              if (!dragRef.current.moved) {
                onClearSelection();
              }
            }}
          />

          {/* Subdued surrounding background geography (is_playable = false) */}
          <g className="map-background-regions">
            {BACKGROUND_REGION_GEOMETRIES.map((bg) => (
              <path
                key={bg.province_id}
                d={bg.svgPath}
                data-province-id={bg.province_id}
                data-is-playable="false"
                className="map-bg-polygon"
                fill={SEVERITY_FILL_MAP.background}
                stroke={SEVERITY_STROKE_MAP.background}
                strokeWidth="1.5"
                strokeDasharray="4 2"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!dragRef.current.moved) {
                    onClearSelection();
                  }
                }}
              />
            ))}
          </g>

          {/* Classical ink-wash mountain ranges in background terrain (matching ui-layout-v1.png) */}
          <g className="map-terrain-mountains" pointerEvents="none">
            {/* Northwest mountain range */}
            <path
              d="M 8 142 Q 28 96 48 64 Q 68 92 86 112 Q 110 68 134 38 Q 158 78 178 106 Q 198 76 218 54 Q 242 94 264 126 Q 282 104 298 88 Q 318 118 342 146 Z"
              fill="url(#mountain-ink-grad)"
              stroke="none"
            />
            <path
              d="M 8 142 Q 28 96 48 64 Q 68 92 86 112 Q 110 68 134 38 Q 158 78 178 106 Q 198 76 218 54 Q 242 94 264 126 Q 282 104 298 88 Q 318 118 342 146"
              fill="none"
              stroke="#6c6357"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
            <path
              d="M 0 220 Q 20 186 38 164 Q 58 188 78 206 Q 98 174 118 152 Q 142 184 168 216 Z"
              fill="url(#mountain-ink-grad)"
              stroke="none"
            />
            <path
              d="M 0 220 Q 20 186 38 164 Q 58 188 78 206 Q 98 174 118 152 Q 142 184 168 216"
              fill="none"
              stroke="#756b5e"
              strokeWidth="1.3"
              strokeLinecap="round"
            />
            {/* Southwest / South ridges */}
            <path
              d="M 44 570 Q 72 526 98 494 Q 122 528 146 552 Q 170 512 194 482 Q 224 524 252 558 Q 276 530 298 508 Q 324 542 352 574 Z"
              fill="url(#mountain-ink-grad)"
              stroke="none"
            />
            <path
              d="M 44 570 Q 72 526 98 494 Q 122 528 146 552 Q 170 512 194 482 Q 224 524 252 558 Q 276 530 298 508 Q 324 542 352 574"
              fill="none"
              stroke="#6c6357"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <path
              d="M 28 682 Q 56 638 84 608 Q 112 640 138 664 Q 164 624 188 594 Q 218 636 246 668 Q 278 638 308 614 Q 338 648 370 684 Z"
              fill="url(#mountain-ink-grad)"
              stroke="none"
            />
            <path
              d="M 28 682 Q 56 638 84 608 Q 112 640 138 664 Q 164 624 188 594 Q 218 636 246 668 Q 278 638 308 614 Q 338 648 370 684"
              fill="none"
              stroke="#756b5e"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
            {/* Southeast grand mountain range */}
            <path
              d="M 552 652 Q 584 598 614 558 Q 642 596 668 626 Q 698 576 728 534 Q 760 580 792 618 Q 824 580 854 550 Q 886 598 916 638 Q 942 606 968 580 Q 998 618 1032 656 Z"
              fill="url(#mountain-ink-grad)"
              stroke="none"
            />
            <path
              d="M 552 652 Q 584 598 614 558 Q 642 596 668 626 Q 698 576 728 534 Q 760 580 792 618 Q 824 580 854 550 Q 886 598 916 638 Q 942 606 968 580 Q 998 618 1032 656"
              fill="none"
              stroke="#685f53"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
            <path
              d="M 608 706 Q 642 656 674 620 Q 704 656 734 686 Q 766 638 796 600 Q 830 648 864 688 Q 896 648 928 618 Q 964 662 1002 706 Z"
              fill="url(#mountain-ink-grad)"
              stroke="none"
            />
            <path
              d="M 608 706 Q 642 656 674 620 Q 704 656 734 686 Q 766 638 796 600 Q 830 648 864 688 Q 896 648 928 618 Q 964 662 1002 706"
              fill="none"
              stroke="#73695c"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
            {/* Eastern hills */}
            <path
              d="M 880 364 Q 902 334 924 312 Q 944 338 964 356 Q 984 328 1004 304 Q 1028 334 1056 364 Z"
              fill="url(#mountain-ink-grad)"
              stroke="none"
            />
            <path
              d="M 880 364 Q 902 334 924 312 Q 944 338 964 356 Q 984 328 1004 304 Q 1028 334 1056 364"
              fill="none"
              stroke="#786e60"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
          </g>

          {/* River network */}
          <g className="map-rivers" pointerEvents="none">
            {MAP_RIVER_PATHS.map((river) => (
              <g key={river.id}>
                <path
                  d={river.d}
                  fill="none"
                  stroke="#b7cbd6"
                  strokeWidth={river.strokeWidth + 2}
                  strokeLinecap="round"
                  opacity="0.55"
                />
                <path
                  d={river.d}
                  fill="none"
                  stroke="#6898b5"
                  strokeWidth={river.strokeWidth}
                  strokeLinecap="round"
                  opacity="0.88"
                />
              </g>
            ))}
          </g>

          {/* Background region labels */}
          <g className="map-background-labels" pointerEvents="none">
            {BACKGROUND_REGION_GEOMETRIES.filter((b) => b.showLabel).map((bg) => (
              <g key={`label-${bg.province_id}`} transform={`translate(${bg.center.x}, ${bg.center.y})`}>
                <text
                  textAnchor="middle"
                  y="-6"
                  fill="#787065"
                  fontSize="17"
                  fontWeight="600"
                  letterSpacing="1.5"
                >
                  {bg.display_title}
                </text>
                <text
                  textAnchor="middle"
                  y="16"
                  fill="#877e72"
                  fontSize="14"
                  letterSpacing="1"
                >
                  {bg.display_subtitle}
                </text>
              </g>
            ))}
          </g>

          {/* Playable states (甲州, 乙州, 丙州) */}
          <g className="map-playable-states">
            {PLAYABLE_PROVINCE_GEOMETRIES.map((geom) => {
              const stateData = states.find((s) => s.state_id === geom.state_id);
              if (!stateData) return null;

              const presentation = computeStateLayerPresentation(stateData, activeLayer);
              const isSelected = selectedStateId === geom.state_id;
              const isHovered = hoveredStateId === geom.state_id;
              const fill = SEVERITY_FILL_MAP[presentation.severityKey];
              const stroke = isSelected
                ? '#f6d27a'
                : isHovered
                  ? '#3d2914'
                  : SEVERITY_STROKE_MAP[presentation.severityKey];

              const stateDebug = debugTruth?.states.find((s) => s.state_id === geom.state_id);

              return (
                <g
                  key={geom.state_id}
                  className={`map-playable-province ${isSelected ? 'is-selected' : ''}`}
                  data-testid={`map-state-${geom.state_id}`}
                  data-state-id={geom.state_id}
                  data-is-playable="true"
                  data-report-status={stateData.report_status}
                  data-visual-severity={presentation.severityKey}
                  onMouseEnter={() => setHoveredStateId(geom.state_id)}
                  onMouseLeave={() =>
                    setHoveredStateId((prev) => (prev === geom.state_id ? null : prev))
                  }
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!dragRef.current.moved) {
                      const currentWidth =
                        containerRef.current?.clientWidth || viewportWidth || 1280;
                      onSelectState(geom.state_id, currentWidth);
                    }
                  }}
                >
                  <path
                    d={geom.svgPath}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={isSelected ? 4 : isHovered ? 2.8 : 2}
                    strokeLinejoin="round"
                    filter={isSelected ? 'url(#selected-state-glow)' : undefined}
                    style={{ cursor: 'pointer', transition: 'stroke-width 0.15s ease' }}
                  />

                  {/* Flood wave / Drought emblem above state label */}
                  {presentation.showFloodWaveIcon && (
                    <g
                      transform={`translate(${geom.labelAnchor.x}, ${geom.labelAnchor.y - 56})`}
                      pointerEvents="none"
                    >
                      <circle cx="0" cy="0" r="18" fill="#8f2c22" stroke="#f5dec0" strokeWidth="1.8" />
                      <path
                        d="M -10 -3 Q -5 -8 0 -3 T 10 -3 M -10 4 Q -5 -1 0 4 T 10 4"
                        fill="none"
                        stroke="#fff6e8"
                        strokeWidth="2.3"
                        strokeLinecap="round"
                      />
                    </g>
                  )}

                  {presentation.showDroughtSunIcon && (
                    <g
                      transform={`translate(${geom.labelAnchor.x}, ${geom.labelAnchor.y - 56})`}
                      pointerEvents="none"
                    >
                      <circle cx="0" cy="0" r="16" fill="#c76e22" stroke="#f5dec0" strokeWidth="1.6" />
                      <circle cx="0" cy="0" r="6.5" fill="#fff2d6" />
                    </g>
                  )}

                  {/* State Name & Scroll Plate */}
                  <g
                    transform={`translate(${geom.labelAnchor.x}, ${geom.labelAnchor.y})`}
                    pointerEvents="none"
                  >
                    <text
                      textAnchor="middle"
                      y="-8"
                      fill={presentation.severityKey === 'unknown' ? '#f7f1e6' : '#241a10'}
                      stroke={presentation.severityKey === 'unknown' ? '#2b251f' : '#efe5d2'}
                      strokeWidth="0.6"
                      fontSize="24"
                      fontWeight="800"
                      letterSpacing="2"
                    >
                      {geom.state_name}
                    </text>

                    {/* Scroll plaque for report status / metric */}
                    <rect
                      x="-84"
                      y="4"
                      width="168"
                      height="28"
                      rx="5"
                      fill={isSelected ? '#fbf1dc' : '#f4e8cf'}
                      stroke={isSelected ? '#9e3424' : '#7b5f3d'}
                      strokeWidth={isSelected ? '2' : '1.4'}
                    />
                    <text
                      textAnchor="middle"
                      y="23"
                      fill={
                        presentation.severityKey === 'urgent'
                          ? '#8c1f16'
                          : presentation.severityKey === 'unknown'
                            ? '#49423b'
                            : '#332415'
                      }
                      fontSize="13.5"
                      fontWeight="700"
                    >
                      {presentation.badgeSubtitle}
                    </text>

                    {/* Debug truth overlay badge when debug mode is active */}
                    {stateDebug && (
                      <g transform="translate(0, 38)">
                        <rect
                          x="-92"
                          y="0"
                          width="184"
                          height="22"
                          rx="4"
                          fill="#1f2937"
                          stroke="#f59e0b"
                          strokeWidth="1.2"
                        />
                        <text
                          textAnchor="middle"
                          y="15"
                          fill="#fde68a"
                          fontSize="11.5"
                          fontWeight="600"
                        >
                          {`[真值] 可支配粮${formatWan(stateDebug.truth.disposable_grain, '万石')} · 银${formatWan(stateDebug.truth.disposable_silver, '万两')}`}
                        </text>
                      </g>
                    )}
                  </g>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* Hover lightweight floating tooltip */}
      {hoveredState && hoveredPresentation && (
        <div
          className="map-hover-tooltip"
          data-testid="map-hover-tooltip"
          style={{
            left: `${Math.min(viewportWidth - 280, Math.max(16, hoverPos.x + 14))}px`,
            top: `${Math.max(16, hoverPos.y - 24)}px`,
          }}
        >
          {hoveredPresentation.tooltipLines.map((line, idx) => (
            <div key={idx} className={idx === 0 ? 'tooltip-title' : 'tooltip-line'}>
              {line}
            </div>
          ))}
        </div>
      )}

      {/* Compact Camera Controls (Top-Left of map canvas) */}
      <div className="map-camera-controls" aria-label="地图视角控制">
        <button
          type="button"
          className="camera-btn"
          title="放大地图"
          onClick={() => adjustZoom(0.2)}
        >
          ＋
        </button>
        <button
          type="button"
          className="camera-btn"
          title="缩小地图"
          onClick={() => adjustZoom(-0.2)}
        >
          －
        </button>
        <button
          type="button"
          className="camera-btn camera-btn-text"
          title="重置地图中心与缩放"
          onClick={() => onChangeCamera(INITIAL_MAP_CAMERA)}
        >
          重置视角
        </button>
      </div>

      {/* Bottom-Left Compact Layer Capsule & 5-State Honest Legend */}
      <div className="map-layer-capsule" data-testid="map-layer-capsule">
        <div className="layer-switcher-row" role="tablist" aria-label="地图图层切换">
          <button
            type="button"
            role="tab"
            aria-selected={activeLayer === 'disaster'}
            className={`layer-tab-btn ${activeLayer === 'disaster' ? 'active' : ''}`}
            data-testid="layer-btn-disaster"
            onClick={() => onChangeLayer('disaster')}
          >
            灾情赈济
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeLayer === 'grain'}
            className={`layer-tab-btn ${activeLayer === 'grain' ? 'active' : ''}`}
            data-testid="layer-btn-grain"
            onClick={() => onChangeLayer('grain')}
          >
            存粮上报
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeLayer === 'silver'}
            className={`layer-tab-btn ${activeLayer === 'silver' ? 'active' : ''}`}
            data-testid="layer-btn-silver"
            onClick={() => onChangeLayer('silver')}
          >
            存银上报
          </button>
        </div>

        <div className="legend-items-row" data-testid="map-legend-items">
          {legendEntries.map((item) => (
            <span
              key={item.key}
              className="legend-chip"
              data-legend-key={item.key}
              title={item.detailLabel}
            >
              <span className={`legend-swatch swatch-${item.key}`} />
              <span className="legend-text">{item.shortLabel}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
