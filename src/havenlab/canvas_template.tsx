import {
  BarChart,
  Callout,
  Divider,
  H1,
  H2,
  LineChart,
  Pill,
  Row,
  Select,
  Stack,
  Stat,
  Table,
  Text,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

type Num = number | null;

type Lab = {
  meta: {
    sample_start: string;
    sample_end: string;
    n_months: number;
    var_lags: number;
    var_t: number;
    var_boot: number;
    built: string;
  };
  months: string[];
  ret: Record<string, Num[]>;
  dgpr: Num[];
  gpr: Num[];
  haven: { score: Num[]; high: Num[] };
  heatmap: { labels: string[]; pairs: { id: string; name: string; values: Num[] }[] };
  var: {
    lags: number;
    t: number;
    order: string[];
    units: string[];
    keys: string[];
    horizon: number[];
    cum: Record<string, number[]>;
    boot_kept: number;
  };
  events: {
    id: string;
    date: string;
    month: string;
    group: string;
    name: string;
    note: string;
    path: Record<string, Num[]>;
  }[];
  path_origin: number;
};

const LAB = JSON.parse(`__CANVAS_JSON__`) as Lab;

const ASSETS = ["gold", "brent", "dxy", "csi", "hsi"] as const;
const NAMES: Record<string, string> = {
  gold: "黄金",
  brent: "布伦特",
  dxy: "美元指数",
  csi: "沪深300",
  hsi: "恒生",
};
const PAIRS: { key: string; left: string; right: string }[] = [
  { key: "布伦特", left: "gold", right: "brent" },
  { key: "美元", left: "gold", right: "dxy" },
  { key: "沪深300", left: "gold", right: "csi" },
  { key: "恒生", left: "gold", right: "hsi" },
  { key: "GPR变动", left: "gold", right: "dgpr" },
];

function corr(xs: Num[], ys: Num[]): number | null {
  const buf: [number, number][] = [];
  for (let i = 0; i < xs.length; i++) {
    const x = xs[i];
    const y = ys[i];
    if (x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y)) continue;
    buf.push([x, y]);
  }
  const n = buf.length;
  if (n < 4) return null;
  let mx = 0;
  let my = 0;
  for (const [x, y] of buf) {
    mx += x;
    my += y;
  }
  mx /= n;
  my /= n;
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (const [x, y] of buf) {
    const a = x - mx;
    const b = y - my;
    num += a * b;
    dx += a * a;
    dy += b * b;
  }
  if (dx <= 1e-12 || dy <= 1e-12) return null;
  return num / Math.sqrt(dx * dy);
}

function block(a: number, b: number) {
  return {
    gold: LAB.ret.gold.slice(a, b),
    brent: LAB.ret.brent.slice(a, b),
    dxy: LAB.ret.dxy.slice(a, b),
    csi: LAB.ret.csi.slice(a, b),
    hsi: LAB.ret.hsi.slice(a, b),
    dgpr: LAB.dgpr.slice(a, b),
    gpr: LAB.gpr.slice(a, b),
  };
}

function finiteSum(arr: Num[]) {
  let sum = 0;
  let n = 0;
  for (const value of arr) {
    if (value == null || !Number.isFinite(value)) continue;
    sum += value;
    n += 1;
  }
  return { sum: n ? sum : null, n };
}

function havenScore(part: ReturnType<typeof block>) {
  const cCsi = corr(part.gold, part.csi);
  const cHsi = corr(part.gold, part.hsi);
  const cGpr = corr(part.gold, part.dgpr);
  const cDxy = corr(part.gold, part.dxy);
  const cBrent = corr(part.gold, part.brent);
  if (cCsi == null || cHsi == null || cGpr == null || cDxy == null) return null;
  const equity = 50 * (1 - (cCsi + cHsi) / 2);
  const gpr = 50 * (1 + cGpr);
  const dollar = 50 * (1 - cDxy);
  return { score: (equity + gpr + dollar) / 3, equity, gpr, dollar, cCsi, cHsi, cGpr, cDxy, cBrent };
}

function analyze(month: string, width: number) {
  const idx = LAB.months.indexOf(month);
  if (idx < 0) return null;
  const n = LAB.months.length;
  const b0 = Math.max(0, idx - width);
  const a1 = Math.min(n, idx + width);
  const before = block(b0, idx);
  const after = block(idx, a1);
  const gold = finiteSum(after.gold);
  const csi = finiteSum(after.csi);
  return {
    partial: b0 !== idx - width || a1 !== idx + width || gold.n < width || csi.n < width,
    nBefore: idx - b0,
    nAfter: gold.n,
    cum: {
      gold: gold.sum,
      brent: finiteSum(after.brent).sum,
      dxy: finiteSum(after.dxy).sum,
      csi: csi.sum,
      hsi: finiteSum(after.hsi).sum,
    },
    before: havenScore(before),
    after: havenScore(after),
    gprBefore: (() => {
      const got = finiteSum(before.gpr);
      return got.n ? (got.sum as number) / got.n : null;
    })(),
    gprAfter: (() => {
      const got = finiteSum(after.gpr);
      return got.n ? (got.sum as number) / got.n : null;
    })(),
  };
}

function fmt(value: number | null, digits = 1) {
  if (value == null || !Number.isFinite(value)) return "—";
  const text = value.toFixed(digits);
  return value > 0 ? `+${text}` : text;
}

function claim(stats: NonNullable<ReturnType<typeof analyze>>) {
  const gold = stats.cum.gold;
  const csi = stats.cum.csi;
  const brent = stats.cum.brent;
  if (gold != null && csi != null && gold > 0 && csi < 0) return "黄金上涨而沪深300下跌，价格路径与避险分流一致。";
  if (brent != null && gold != null && brent > 0 && gold < 0) return "布伦特上涨而黄金下跌，这段窗口里黄金没有表现出典型的避险上涨。";
  if (gold != null && csi != null && gold < 0 && csi < 0) return "黄金与沪深300同时下跌，更像流动性和实际利率一起抽紧。";
  if (gold != null && csi != null && gold > 0 && csi > 0) return "黄金与沪深300同时上涨，避险资产和风险资产没有反向分开。";
  return "这组价格路径没有呈现单一方向。";
}

function Heatmap({ quarter }: { quarter: string }) {
  const theme = useHostTheme();
  const heat = LAB.heatmap;
  const cell = 14;
  const labelW = 108;
  const head = 22;
  const width = labelW + heat.labels.length * cell;
  const height = head + heat.pairs.length * cell;
  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={width} height={height} role="img" aria-label="黄金36个月滚动相关">
        {heat.labels.map((label, index) =>
          label.endsWith("Q1") ? (
            <text key={label} x={labelW + index * cell} y={12} fill={theme.text.tertiary} fontSize={11}>
              {label.slice(0, 4)}
            </text>
          ) : null,
        )}
        {heat.pairs.map((pair, row) => (
          <g key={pair.id}>
            <text x={0} y={head + row * cell + 11} fill={theme.text.primary} fontSize={12}>
              {pair.name}
            </text>
            {pair.values.map((value, col) => {
              const negative = value != null && value < 0;
              return (
                <rect
                  key={`${pair.id}-${heat.labels[col]}`}
                  x={labelW + col * cell}
                  y={head + row * cell}
                  width={cell - 1}
                  height={cell - 1}
                  fill={value == null ? theme.fill.tertiary : negative ? theme.accent.primary : theme.text.secondary}
                  fillOpacity={value == null ? 1 : Math.max(0.12, Math.abs(value))}
                  stroke={heat.labels[col] === quarter ? theme.text.primary : "none"}
                >
                  <title>
                    {pair.name} {heat.labels[col]} {value == null ? "无" : value.toFixed(2)}
                  </title>
                </rect>
              );
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}

export default function GprHavenLab() {
  const [eventId, setEventId] = useCanvasState("event", "hormuz_2026");
  const [sessions, setSessions] = useCanvasState("sessions", 40);
  const [width, setWidth] = useCanvasState("width", 6);
  const event = LAB.events.find((item) => item.id === eventId) ?? LAB.events[LAB.events.length - 1];
  const stats = analyze(event.month, width);
  const origin = LAB.path_origin;
  const taus: number[] = [];
  const paths: Record<string, number[]> = { gold: [], brent: [], dxy: [], csi: [], hsi: [] };
  for (let tau = -sessions; tau < sessions; tau++) {
    const index = tau - origin;
    const values = ASSETS.map((name) => event.path[name][index]);
    if (values.some((value) => value == null || !Number.isFinite(value))) continue;
    taus.push(tau);
    ASSETS.forEach((name, index) => paths[name].push(values[index] as number));
  }
  const gprPath: number[] = [];
  const gprTau: number[] = [];
  for (let tau = -sessions; tau < sessions; tau++) {
    const value = event.path.gpr[tau - origin];
    if (value == null || !Number.isFinite(value)) continue;
    gprTau.push(tau);
    gprPath.push(value);
  }
  const labels = taus.map((tau) => (tau % 20 === 0 || tau === 0 ? String(tau) : ""));
  const gprLabels = gprTau.map((tau) => (tau % 20 === 0 || tau === 0 ? String(tau) : ""));
  const quarter = `${event.month.slice(0, 4)}Q${Math.floor((Number(event.month.slice(5, 7)) - 1) / 3) + 1}`;
  const score = stats?.after?.score ?? null;
  const tone = score == null ? undefined : score >= 60 ? "success" : score < 45 ? "warning" : "info";
  const rows = LAB.events.map((item) => {
    const window = analyze(item.month, width);
    const delta = window?.before && window.after ? window.after.cCsi - window.before.cCsi : null;
    const excess = window?.cum.gold != null && window.cum.csi != null ? window.cum.gold - window.cum.csi : null;
    return [
      item.name,
      fmt(window?.cum.gold ?? null),
      fmt(window?.cum.brent ?? null),
      fmt(window?.cum.csi ?? null),
      fmt(excess),
      delta == null ? "—" : fmt(delta, 2),
      window?.after ? window.after.score.toFixed(0) : "—",
      window ? `${window.nAfter}${window.partial ? "*" : ""}` : "—",
    ];
  });
  const tones = LAB.events.map((item) => {
    const window = analyze(item.month, width);
    if (!window || window.cum.gold == null || window.cum.csi == null || window.cum.brent == null) return undefined;
    if (window.cum.brent > 0 && window.cum.gold < 0) return "warning" as const;
    if (window.cum.gold > 0 && window.cum.csi < 0) return "success" as const;
    return undefined;
  });

  return (
    <Stack gap={16}>
      <Stack gap={4}>
        <H1>地缘政治风险 × 避险资产</H1>
        <Text tone="secondary">
          月度样本 {LAB.meta.sample_start} 至 {LAB.meta.sample_end}，共 {LAB.meta.n_months} 个月。价格路径用交易日，相关和避险强度用月度对数收益。
        </Text>
      </Stack>
      <Row gap={12} align="center" wrap>
        <Select
          value={event.id}
          onChange={setEventId}
          options={LAB.events.map((item) => ({ value: item.id, label: `${item.month}  ${item.name}` }))}
        />
        {[20, 40, 60].map((value) => (
          <Pill key={value} active={sessions === value} onClick={() => setSessions(value)}>
            {value}日
          </Pill>
        ))}
        {[6, 12, 24].map((value) => (
          <Pill key={value} active={width === value} onClick={() => setWidth(value)}>
            {value}个月
          </Pill>
        ))}
      </Row>
      {stats ? (
        <Callout tone={stats.cum.brent != null && stats.cum.gold != null && stats.cum.brent > 0 && stats.cum.gold < 0 ? "warning" : "info"} title={event.name}>
          {event.date} 之后 {stats.nAfter} 个月：黄金 {fmt(stats.cum.gold)}%，布伦特 {fmt(stats.cum.brent)}%，沪深300 {fmt(stats.cum.csi)}%，恒生 {fmt(stats.cum.hsi)}%。
          {stats.before && stats.after ? ` 黄金与沪深300的相关由 ${stats.before.cCsi.toFixed(2)} 变为 ${stats.after.cCsi.toFixed(2)}。` : ""}
          {claim(stats)}
          {stats.partial ? " 事后窗口被样本末端截断。" : ""}
          这是窗口内的描述，不是因果识别。
        </Callout>
      ) : null}
      <Text tone="secondary" size="small">{event.note}</Text>
      <Row gap={16} wrap>
        <Stat value={score == null ? "—" : score.toFixed(0)} label="避险强度（事后）" tone={tone} />
        <Stat value={`${fmt(stats?.cum.gold ?? null)}%`} label="黄金累计对数收益" />
        <Stat value={`${fmt(stats?.cum.brent ?? null)}%`} label="布伦特累计对数收益" />
        <Stat value={`${fmt(stats?.cum.csi ?? null)}%`} label="沪深300累计对数收益" />
        <Stat
          value={stats?.gprAfter == null ? "—" : `${Math.round(stats.gprAfter)}`}
          label={stats?.gprBefore == null ? "事后 GPR 月均" : `事后 GPR 月均，事前 ${Math.round(stats.gprBefore)}`}
        />
      </Row>
      <H2>事件前后价格路径</H2>
      <Text tone="tertiary" size="small">
        指数，事件前最后收盘 = 100。横轴是各市场自己的交易日，0 为事件日或其后第一个交易日。来源：Yahoo GC=F、BZ=F、DX-Y.NYB、^HSI，新浪沪深300。
      </Text>
      <LineChart
        height={280}
        categories={labels}
        beginAtZero={false}
        series={ASSETS.map((name) => ({ name: NAMES[name], data: paths[name] }))}
        referenceLines={[{ value: 100, label: "事件前收盘" }]}
      />
      <H2>GPR 日度水平</H2>
      <Text tone="tertiary" size="small">
        Caldara–Iacoviello GPRD，按黄金交易日对齐。纵轴是指数点。下载日期 {LAB.meta.built}。
      </Text>
      <LineChart
        height={160}
        categories={gprLabels}
        beginAtZero={false}
        series={[{ name: "GPRD", data: gprPath, tone: "neutral" }]}
      />
      <H2>事件前后相关系数</H2>
      <Text tone="tertiary" size="small">
        事前 {stats?.nBefore ?? "—"} 个月，不含事件月；事后 {stats?.nAfter ?? "—"} 个月，含事件月。纵轴是皮尔逊相关系数。
      </Text>
      {stats?.before && stats.after ? (
        <BarChart
          height={220}
          categories={PAIRS.map((pair) => pair.key)}
          beginAtZero={false}
          yMin={-1}
          yMax={1}
          series={[
            {
              name: "事前",
              tone: "info",
              data: PAIRS.map((pair) => stats.before?.[pair.right === "dgpr" ? "cGpr" : pair.right === "brent" ? "cBrent" : pair.right === "dxy" ? "cDxy" : pair.right === "csi" ? "cCsi" : "cHsi"] ?? 0),
            },
            {
              name: "事后",
              tone: "warning",
              data: PAIRS.map((pair) => stats.after?.[pair.right === "dgpr" ? "cGpr" : pair.right === "brent" ? "cBrent" : pair.right === "dxy" ? "cDxy" : pair.right === "csi" ? "cCsi" : "cHsi"] ?? 0),
            },
          ]}
        />
      ) : (
        <Text tone="secondary">这个窗口的月份太少，相关没有计算。</Text>
      )}
      <H2>同一窗口下的全部事件</H2>
      <Table
        headers={["事件", "黄金", "布伦特", "沪深300", "黄金−沪深300", "相关变化", "避险强度", "月数"]}
        columnAlign={["left", "right", "right", "right", "right", "right", "right", "right"]}
        rows={rows}
        rowTone={tones}
        striped
      />
      <Text tone="tertiary" size="small">
        收益单位是百分点。相关变化是黄金与沪深300的事后减事前。橙色点标出布伦特上涨且黄金下跌的窗口。* 表示窗口不完整。
      </Text>
      <Divider />
      <H2>36 个月滚动相关</H2>
      <Text tone="tertiary" size="small">
        每一格止于该季末。蓝色偏负，灰色偏正。黑框是 {quarter}。
      </Text>
      <Heatmap quarter={quarter} />
      <H2>GPR 冲击的累计脉冲响应</H2>
      <Text tone="tertiary" size="small">
        递归 VAR {LAB.var.lags} 阶，T={LAB.var.t}。顺序：{LAB.var.order.join("、")}。纵轴是月度对数收益百分点的累加，近似价格水平变化。90% 区间在论文图里，这里只画点估计。保留自助样本 {LAB.var.boot_kept} 次。不是结构因果。
      </Text>
      <LineChart
        height={220}
        categories={LAB.var.horizon.map(String)}
        beginAtZero={false}
        series={["ret_brent", "ret_gold", "ret_dxy", "ret_csi", "ret_hsi"].map((key) => ({
          name: NAMES[key.replace("ret_", "")],
          data: LAB.var.cum[key],
        }))}
        referenceLines={[{ value: 0, label: "0" }]}
        valueSuffix="%"
      />
      <LineChart
        height={160}
        categories={LAB.var.horizon.map(String)}
        beginAtZero={false}
        series={[{ name: "GPR变动", data: LAB.var.cum.dgpr, tone: "neutral" }]}
        referenceLines={[{ value: 0, label: "0" }]}
      />
      <Text tone="tertiary" size="small">
        GPR 面板的纵轴是指数点。样本内，1 个标准差的正向 GPR 冲击之后，布伦特的点估计上升，黄金和股指的点估计接近零，90% 区间都覆盖零。平均冲击解释不了单次事件。
      </Text>
    </Stack>
  );
}
