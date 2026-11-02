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
    return () => window.removeEventListener('resize', updateSize);
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
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest('.map-layer-capsule') || target.closest('.map-camera-controls')) {
      return;
    }
    e.preventDefault();
    const rect = containerRef.current?.getBoundingClientRect();
    const cursorX = rect ? e.clientX - rect.left : viewportWidth / 2;
    const cursorY = rect ? e.clientY - rect.top : 354;

    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
    const nextZoom = Math.min(2.4, Math.max(0.65, Number((camera.zoom * zoomFactor).toFixed(3))));
    if (nextZoom === camera.zoom) return;

    const scaleRatio = nextZoom / camera.zoom;
    const nextPanX = Math.round((cursorX - (cursorX - camera.panX) * scaleRatio) * 100) / 100;
    const nextPanY = Math.round((cursorY - (cursorY - camera.panY) * scaleRatio) * 100) / 100;

    onChangeCamera({
      panX: nextPanX,
      panY: nextPanY,
      zoom: nextZoom,
    });
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
      onWheel={handleWheel}
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
          aria-label="江山與州郡與奏报與图"
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
              d="M 12 138 L 48 68 L 86 112 L 132 42 L 178 106 L 216 58 L 264 128 L 296 92 L 336 144 Z"
              fill="url(#mountain-ink-grad)"
              stroke="#6c6459"
              strokeWidth="1.3"
            />
            <path
              d="M 0 218 L 36 168 L 78 206 L 116 154 L 164 214 Z"
              fill="url(#mountain-ink-grad)"
              stroke="#6c6459"
              strokeWidth="1.1"
            />
            {/* Southwest / South ridges */}
            <path
              d="M 48 566 L 98 498 L 146 552 L 194 486 L 252 558 L 298 512 L 348 574 Z"
              fill="url(#mountain-ink-grad)"
              stroke="#6c6459"
              strokeWidth="1.3"
            />
            <path
              d="M 32 678 L 84 612 L 138 664 L 188 598 L 246 668 L 308 618 L 366 682 Z"
              fill="url(#mountain-ink-grad)"
              stroke="#6c6459"
              strokeWidth="1.2"
            />
            {/* Southeast grand mountain range */}
            <path
              d="M 556 648 L 614 562 L 668 626 L 728 538 L 792 618 L 854 554 L 916 638 L 968 584 L 1028 654 Z"
              fill="url(#mountain-ink-grad)"
              stroke="#6c6459"
              strokeWidth="1.4"
            />
            <path
              d="M 612 706 L 674 624 L 734 686 L 796 604 L 864 688 L 928 622 L 998 706 Z"
              fill="url(#mountain-ink-grad)"
              stroke="#6c6459"
              strokeWidth="1.3"
            />
            {/* Eastern hills */}
            <path
              d="M 884 362 L 924 316 L 964 356 L 1004 308 L 1052 362 Z"
              fill="url(#mountain-ink-grad)"
              stroke="#6c6459"
              strokeWidth="1.1"
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
                      transform={`translate(${geom.labelAnchor.x}, ${geom.labelAnchor.y - 44})`}
                      pointerEvents="none"
                    >
                      <circle cx="0" cy="0" r="19" fill="#8f2c22" stroke="#f5dec0" strokeWidth="1.8" />
                      <path
                        d="M -11 -3 Q -5 -9 0 -3 T 11 -3 M -11 4 Q -5 -2 0 4 T 11 4"
                        fill="none"
                        stroke="#fff6e8"
                        strokeWidth="2.4"
                        strokeLinecap="round"
                      />
                    </g>
                  )}

                  {presentation.showDroughtSunIcon && (
                    <g
                      transform={`translate(${geom.labelAnchor.x}, ${geom.labelAnchor.y - 44})`}
                      pointerEvents="none"
                    >
                      <circle cx="0" cy="0" r="17" fill="#c76e22" stroke="#f5dec0" strokeWidth="1.6" />
                      <circle cx="0" cy="0" r="7" fill="#fff2d6" />
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
