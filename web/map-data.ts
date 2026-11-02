import {
  formatWan,
  type CourtStateView,
  type MapReportSeverity,
  type StateId,
} from '../src/contracts/index.ts';

export const MAP_VIEWBOX_WIDTH = 1280;
export const MAP_VIEWBOX_HEIGHT = 708;

export type MapLayerKind = 'disaster' | 'grain' | 'silver';

export interface MapCameraState {
  panX: number;
  panY: number;
  zoom: number;
}

export const INITIAL_MAP_CAMERA: MapCameraState = {
  panX: 0,
  panY: 0,
  zoom: 1,
};

export interface PlayableProvinceGeometry {
  state_id: StateId;
  state_name: string;
  is_playable: true;
  center: { x: number; y: number };
  labelAnchor: { x: number; y: number };
  svgPath: string;
}

export interface BackgroundRegionGeometry {
  province_id: string;
  region_name: string;
  display_title: string;
  display_subtitle: '(未启用)';
  is_playable: false;
  center: { x: number; y: number };
  showLabel: boolean;
  svgPath: string;
}

// Original neutral cartographic polygons tiling the 1280x708 parchment canvas.
// Playable states (甲州, 乙州, 丙州) occupy the central river basin; surrounding regions are subdued background geography.
export const PLAYABLE_PROVINCE_GEOMETRIES: readonly PlayableProvinceGeometry[] = [
  {
    state_id: 'state_a',
    state_name: '甲州',
    is_playable: true,
    center: { x: 325, y: 332 },
    labelAnchor: { x: 322, y: 325 },
    svgPath:
      'M 235 232 L 266 218 L 298 228 L 325 208 L 362 214 L 392 195 L 424 212 L 444 235 L 434 268 L 418 292 L 428 322 L 446 346 L 435 378 L 412 406 L 396 426 L 365 415 L 332 424 L 302 444 L 268 432 L 246 402 L 238 366 L 216 336 L 222 296 L 214 262 Z',
  },
  {
    state_id: 'state_b',
    state_name: '乙州',
    is_playable: true,
    center: { x: 515, y: 348 },
    labelAnchor: { x: 516, y: 342 },
    svgPath:
      'M 444 235 L 478 222 L 512 232 L 548 206 L 584 214 L 614 236 L 632 268 L 622 302 L 636 332 L 624 365 L 594 388 L 578 418 L 548 438 L 512 434 L 478 456 L 446 472 L 412 454 L 396 426 L 412 406 L 435 378 L 446 346 L 428 322 L 418 292 L 434 268 Z',
  },
  {
    state_id: 'state_c',
    state_name: '丙州',
    is_playable: true,
    center: { x: 724, y: 362 },
    labelAnchor: { x: 724, y: 356 },
    svgPath:
      'M 632 268 L 668 254 L 708 264 L 748 242 L 788 252 L 826 276 L 852 308 L 866 346 L 848 384 L 824 416 L 792 432 L 762 462 L 724 474 L 692 452 L 656 444 L 618 428 L 578 418 L 594 388 L 624 365 L 636 332 L 622 302 Z',
  },
] as const;

export const BACKGROUND_REGION_GEOMETRIES: readonly BackgroundRegionGeometry[] = [
  {
    province_id: 'bg_north',
    region_name: '北境地理背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 372, y: 122 },
    showLabel: true,
    svgPath:
      'M 190 0 L 620 0 L 602 58 L 578 108 L 596 156 L 584 214 L 548 206 L 512 232 L 478 222 L 444 235 L 424 212 L 392 195 L 362 214 L 325 208 L 298 228 L 266 218 L 235 232 L 202 184 L 184 128 L 198 64 Z',
  },
  {
    province_id: 'bg_northeast',
    region_name: '东北地理背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 792, y: 142 },
    showLabel: true,
    svgPath:
      'M 620 0 L 1040 0 L 1018 76 L 986 142 L 964 208 L 916 248 L 868 264 L 826 276 L 788 252 L 748 242 L 708 264 L 668 254 L 632 268 L 614 236 L 584 214 L 596 156 L 578 108 L 602 58 Z',
  },
  {
    province_id: 'bg_west',
    region_name: '西境地理背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 112, y: 368 },
    showLabel: true,
    svgPath:
      'M 0 165 L 116 148 L 184 128 L 202 184 L 235 232 L 214 262 L 222 296 L 216 336 L 238 366 L 246 402 L 268 432 L 234 476 L 186 518 L 128 548 L 58 564 L 0 572 Z',
  },
  {
    province_id: 'bg_south',
    region_name: '南境地理背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 586, y: 552 },
    showLabel: true,
    svgPath:
      'M 268 432 L 302 444 L 332 424 L 365 415 L 396 426 L 412 454 L 446 472 L 478 456 L 512 434 L 548 438 L 578 418 L 618 428 L 656 444 L 692 452 L 724 474 L 748 532 L 732 608 L 708 708 L 288 708 L 274 618 L 252 536 L 234 476 Z',
  },
  {
    province_id: 'bg_northwest',
    region_name: '西北山地背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 92, y: 78 },
    showLabel: false,
    svgPath: 'M 0 0 L 190 0 L 198 64 L 184 128 L 116 148 L 0 165 Z',
  },
  {
    province_id: 'bg_southwest',
    region_name: '西南山地背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 138, y: 632 },
    showLabel: false,
    svgPath:
      'M 0 572 L 58 564 L 128 548 L 186 518 L 234 476 L 252 536 L 274 618 L 288 708 L 0 708 Z',
  },
  {
    province_id: 'bg_east',
    region_name: '东境地理背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 1052, y: 295 },
    showLabel: false,
    svgPath:
      'M 1040 0 L 1280 0 L 1280 462 L 1168 446 L 1068 428 L 962 414 L 848 384 L 866 346 L 852 308 L 826 276 L 868 264 L 916 248 L 964 208 L 986 142 L 1018 76 Z',
  },
  {
    province_id: 'bg_southeast',
    region_name: '东南山海背景区',
    display_title: '地理背景区',
    display_subtitle: '(未启用)',
    is_playable: false,
    center: { x: 988, y: 576 },
    showLabel: false,
    svgPath:
      'M 848 384 L 962 414 L 1068 428 L 1168 446 L 1280 462 L 1280 708 L 708 708 L 732 608 L 748 532 L 724 474 L 762 462 L 792 432 L 824 416 Z',
  },
] as const;

export interface MapRiversData {
  id: string;
  d: string;
  strokeWidth: number;
}

export const MAP_RIVER_PATHS: readonly MapRiversData[] = [
  {
    id: 'river_main_west_to_east',
    d: 'M 0 342 C 74 328, 134 274, 214 262 C 268 254, 314 242, 362 214 C 412 185, 444 235, 512 292 C 566 338, 608 358, 636 332 C 686 292, 742 308, 826 276 C 892 252, 954 196, 1025 142',
    strokeWidth: 3.2,
  },
  {
    id: 'river_north_branch',
    d: 'M 332 0 C 348 64, 372 132, 392 195 C 408 242, 434 268, 446 346 C 454 402, 446 472, 422 558 C 402 624, 376 668, 358 708',
    strokeWidth: 2.6,
  },
  {
    id: 'river_central_south',
    d: 'M 548 206 C 536 268, 522 332, 548 438 C 568 518, 552 612, 518 708',
    strokeWidth: 2.4,
  },
  {
    id: 'river_east_south',
    d: 'M 748 242 C 742 312, 756 388, 762 462 C 768 534, 812 618, 864 708',
    strokeWidth: 2.2,
  },
] as const;

export interface StateLayerVisualPresentation {
  severityKey: MapReportSeverity;
  badgeTitle: string;
  badgeSubtitle: string;
  tooltipLines: string[];
  showFloodWaveIcon: boolean;
  showDroughtSunIcon: boolean;
}

export interface LayerLegendEntry {
  key: MapReportSeverity;
  shortLabel: string;
  detailLabel: string;
}

export function getLayerLegendEntries(layer: MapLayerKind): readonly LayerLegendEntry[] {
  switch (layer) {
    case 'disaster':
      return [
        { key: 'urgent', shortLabel: '告急', detailLabel: '[红] 告急（奏报需赈 ≥3.0万石）' },
        { key: 'mild', shortLabel: '轻灾', detailLabel: '[橙] 轻灾（奏报需赈 0.1~2.9万石）' },
        { key: 'stable', shortLabel: '安定', detailLabel: '[绿] 安定（奏报无灾）' },
        {
          key: 'unknown',
          shortLabel: '本周未奏报（未知）',
          detailLabel: '[斜纹深灰] 本周未奏报（未知 · 绝不以0代替）',
        },
        {
          key: 'background',
          shortLabel: '地理背景',
          detailLabel: '[浅灰] 地理背景区（未启用）',
        },
      ];
    case 'grain':
      return [
        { key: 'urgent', shortLabel: '告急(0石)', detailLabel: '[红] 奏报可支配粮 0.0万石' },
        { key: 'mild', shortLabel: '偏紧(≤1万石)', detailLabel: '[橙] 奏报可支配粮 ≤1.0万石' },
        { key: 'stable', shortLabel: '充裕(>1万石)', detailLabel: '[绿] 奏报可支配粮 >1.0万石' },
        {
          key: 'unknown',
          shortLabel: '本周未奏报（未知）',
          detailLabel: '[斜纹深灰] 本周未奏报（未知 · 绝不以0代替）',
        },
        {
          key: 'background',
          shortLabel: '地理背景',
          detailLabel: '[浅灰] 地理背景区（未启用）',
        },
      ];
    case 'silver':
      return [
        { key: 'urgent', shortLabel: '告急(0两)', detailLabel: '[红] 奏报可支配银 0.0万两' },
        { key: 'mild', shortLabel: '偏紧(≤0.5万两)', detailLabel: '[橙] 奏报可支配银 ≤0.5万两' },
        { key: 'stable', shortLabel: '充裕(>0.5万两)', detailLabel: '[绿] 奏报可支配银 >0.5万两' },
        {
          key: 'unknown',
          shortLabel: '本周未奏报（未知）',
          detailLabel: '[斜纹深灰] 本周未奏报（未知 · 绝不以0代替）',
        },
        {
          key: 'background',
          shortLabel: '地理背景',
          detailLabel: '[浅灰] 地理背景区（未启用）',
        },
      ];
  }
}

export function computeStateLayerPresentation(
  state: CourtStateView,
  layer: MapLayerKind,
): StateLayerVisualPresentation {
  if (state.report_status === 'UNKNOWN' || !state.report) {
    return {
      severityKey: 'unknown',
      badgeTitle: state.state_name,
      badgeSubtitle: '本周未奏报（未知）',
      tooltipLines: [
        `${state.state_name}（${state.officer_title}）`,
        '状态：本周未奏报（未知）',
        '说明：尚未收到正式奏报，普通视图绝不读取真值或以 0 代替',
      ],
      showFloodWaveIcon: false,
      showDroughtSunIcon: false,
    };
  }

  const report = state.report;
  const proposal = state.proposal;

  if (layer === 'disaster') {
    const isUrgent = state.map_severity === 'urgent';
    const badgeTitle =
      report.disaster_type === 'none'
        ? state.state_name
        : isUrgent
          ? `${state.state_name}·${report.disaster_label}急递`
          : state.state_name;

    let badgeSubtitle = report.map_badge_label;
    if (report.disaster_type !== 'none') {
      if (isUrgent) {
        badgeSubtitle =
          proposal && proposal.relief_central_grain > 0
            ? `需赈${formatWan(report.relief_demand_grain, '万石')}·请粮${formatWan(proposal.relief_central_grain, '万石')}`
            : `需赈粮${formatWan(report.relief_demand_grain, '万石')}`;
      } else {
        badgeSubtitle =
          proposal && proposal.relief_central_grain > 0
            ? `${report.disaster_label}·请粮${formatWan(proposal.relief_central_grain, '万石')}`
            : `${report.disaster_label}·需赈${formatWan(report.relief_demand_grain, '万石')}`;
      }
    }

    return {
      severityKey: state.map_severity,
      badgeTitle,
      badgeSubtitle,
      tooltipLines: [
        `${state.state_name} · 第${report.week_number}周正式奏报（${state.officer_title}）`,
        `灾情：${report.disaster_label}（奏报需赈粮 ${formatWan(report.relief_demand_grain, '万石')}）`,
        report.disposable_grain_label,
      ],
      showFloodWaveIcon: report.disaster_type === 'flood',
      showDroughtSunIcon: report.disaster_type === 'drought',
    };
  }

  if (layer === 'grain') {
    const dispGrain = report.disposable_grain;
    const severityKey: MapReportSeverity =
      dispGrain === 0 ? 'urgent' : dispGrain <= 10_000 ? 'mild' : 'stable';
    return {
      severityKey,
      badgeTitle: state.state_name,
      badgeSubtitle: `可支配粮 ${formatWan(dispGrain, '万石')}（账面${formatWan(report.gross_grain, '万石')}）`,
      tooltipLines: [
        `${state.state_name} · 第${report.week_number}周存粮上报（${state.officer_title}）`,
        report.disposable_grain_label,
        proposal
          ? `提案：本地自救粮 ${formatWan(proposal.relief_local_grain, '万石')} / 请中央拨粮 ${formatWan(proposal.relief_central_grain, '万石')}`
          : '提案：尚未附报请粮项',
      ],
      showFloodWaveIcon: false,
      showDroughtSunIcon: false,
    };
  }

  // layer === 'silver'
  const dispSilver = report.disposable_silver;
  const severityKey: MapReportSeverity =
    dispSilver === 0 ? 'urgent' : dispSilver <= 5_000 ? 'mild' : 'stable';
  return {
    severityKey,
    badgeTitle: state.state_name,
    badgeSubtitle: `可支配银 ${formatWan(dispSilver, '万两')}（账面${formatWan(report.gross_silver, '万两')}）`,
    tooltipLines: [
      `${state.state_name} · 第${report.week_number}周存银上报（${state.officer_title}）`,
      report.disposable_silver_label,
      proposal
        ? `提案：本地配套银 ${formatWan(proposal.project_local_silver, '万两')} / 请中央工程银 ${formatWan(proposal.project_central_silver, '万两')}`
        : '提案：尚未附报工程请银项',
    ],
    showFloodWaveIcon: false,
    showDroughtSunIcon: false,
  };
}

export function getStateScreenCenterX(
  stateId: StateId,
  viewportWidth: number,
  camera: MapCameraState,
): number {
  const geom = PLAYABLE_PROVINCE_GEOMETRIES.find((p) => p.state_id === stateId);
  if (!geom || viewportWidth <= 0) {
    return 0;
  }
  const baseX = (geom.center.x / MAP_VIEWBOX_WIDTH) * viewportWidth;
  return baseX * camera.zoom + camera.panX;
}

// Section 4.2: When selecting a playable state with the right drawer open (covering right 25%),
// keep camera still if center is within 0%~72% of viewport width; if occluded in 72%~100%,
// pan horizontally left by the minimal delta so the state's center lands at 60% of viewport width
// without modifying zoom or panY.
export function computeMinimalOcclusionPan(
  stateId: StateId,
  viewportWidth: number,
  camera: MapCameraState,
): MapCameraState {
  if (viewportWidth <= 0) {
    return camera;
  }
  const screenX = getStateScreenCenterX(stateId, viewportWidth, camera);
  const ratioX = screenX / viewportWidth;

  if (ratioX > 0.72) {
    const targetScreenX = 0.6 * viewportWidth;
    const deltaX = targetScreenX - screenX;
    return {
      panX: Math.round((camera.panX + deltaX) * 100) / 100,
      panY: camera.panY,
      zoom: camera.zoom,
    };
  }

  return camera;
}

export function pickDefaultSelectedState(states: CourtStateView[]): StateId {
  const reported = states.filter((s) => s.report_status === 'REPORTED' && s.report !== null);
  if (reported.length === 0) {
    return 'state_b';
  }
  const urgent = reported.find((s) => s.map_severity === 'urgent');
  if (urgent) {
    return urgent.state_id;
  }
  const mild = reported.find((s) => s.map_severity === 'mild');
  if (mild) {
    return mild.state_id;
  }
  return reported[0]!.state_id;
}
