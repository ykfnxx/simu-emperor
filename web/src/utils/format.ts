export function buildWsUrl(): string {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const isDev = window.location.port === '5173' || window.location.hostname === 'localhost';
  const wsHost = isDev ? `${window.location.hostname}:8000` : window.location.host;
  return `${wsProtocol}://${wsHost}/ws`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value);
}

export function formatDate(value: string | null): string {
  if (!value) return '暂无';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

// V4: 1 tick = 1 周, 4 ticks = 1 月, 48 ticks = 1 年
// 雍正元年 = 1723年
const TICKS_PER_YEAR = 48;
const TICKS_PER_MONTH = 4;

export function formatTurn(turn: number): string {
  if (turn === 0) return '雍正1年 1月 第1周';

  const totalYears = Math.floor(turn / TICKS_PER_YEAR);
  const remainingTicks = turn % TICKS_PER_YEAR;
  const month = Math.floor(remainingTicks / TICKS_PER_MONTH) + 1;
  const week = (remainingTicks % TICKS_PER_MONTH) + 1;

  const year = totalYears + 1;

  return `雍正${year}年${month}月 第${week}周`;
}
