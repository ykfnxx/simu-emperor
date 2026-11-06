---
name: Simu-Emperor
description: Kimi v4 desktop court HUD with navy and brass framing, paper conversations, and a four-color Ming atlas.
colors:
  panel: "#23404f"
  panel-low: "#1d3543"
  panel-deep: "#1a2f3d"
  text: "#f4ead6"
  muted: "#c2b79c"
  faint: "#8e9a9c"
  brass: "#d0aa5a"
  bright: "#f2d58a"
  line: "rgba(208, 170, 90, 0.26)"
  line-soft: "rgba(208, 170, 90, 0.14)"
  red: "#9c3226"
  action-top: "#a6382a"
  action-bottom: "#8e2b21"
  ink: "#3a2f1f"
  paper-title: "#33291a"
  paper: "#f0e7d1"
  paper-low: "#e7dabd"
  paper-card: "#f8f2e2"
  paper-muted: "#6d5d3d"
  paper-line: "rgba(120, 95, 45, 0.22)"
  paper-border: "rgba(120, 95, 45, 0.45)"
  map-ocean: "#98bacd"
  province-gold: "#c3b176"
  province-sage: "#8da98f"
  province-clay: "#c09280"
  province-slate: "#9caabe"
typography:
  display:
    fontFamily: "CourtSans, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "18px"
    fontWeight: 650
    lineHeight: 1.65
  headline:
    fontFamily: "CourtSans, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.65
  title:
    fontFamily: "CourtSans, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "16px"
    fontWeight: 650
    lineHeight: 1.65
  body:
    fontFamily: "CourtSans, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.65
  conversation:
    fontFamily: "CourtSans, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "CourtSans, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.65
rounded:
  tag: "6px"
  compact: "8px"
  action: "9px"
  card: "10px"
  contact: "11px"
  panel: "14px"
  dialog: "16px"
  circular: "50%"
spacing:
  micro: "4px"
  compact: "6px"
  small: "8px"
  control: "10px"
  content: "12px"
  section: "16px"
  inset: "20px"
  edge: "24px"
components:
  button-primary:
    backgroundColor: "{colors.action-top}"
    textColor: "#fdf0d6"
    rounded: "{rounded.action}"
    padding: "7px 18px"
  button-secondary:
    backgroundColor: "rgba(208, 170, 90, 0.08)"
    textColor: "{colors.text}"
    rounded: "{rounded.compact}"
    padding: "6px 12px"
  button-paper:
    backgroundColor: "rgba(255, 255, 255, 0.38)"
    textColor: "#5c4b2c"
    rounded: "{rounded.compact}"
    padding: "5px 10px"
  chat-input:
    backgroundColor: "rgba(255, 255, 255, 0.58)"
    textColor: "{colors.paper-title}"
    typography: "{typography.conversation}"
    rounded: "{rounded.card}"
    padding: "9px 12px"
  province-tab:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    padding: "0 0 8px"
  mention-chip:
    backgroundColor: "rgba(255, 255, 255, 0.35)"
    textColor: "{colors.paper-muted}"
    rounded: "{rounded.tag}"
    padding: "3px 9px"
  navy-panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
  paper-dialog:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.dialog}"
    width: "min(580px, calc(100vw - 80px))"
  overview-row:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.compact}"
    padding: "6px 9px"
  agent-bubble:
    backgroundColor: "{colors.paper-card}"
    textColor: "#3a3123"
    typography: "{typography.conversation}"
    padding: "10px 14px"
---

# Design System: Simu-Emperor

## Overview

**Creative North Star: "深蓝朝堂与纸面奏对"**

两京十三省 HUD 采用 Kimi v4 已确认的视觉方向：连续地理底图上悬浮深蓝政务框架，中央御前密谈及受保护的对话框使用暖纸面。黄铜细线、短角饰和圆形人物画像建立朝堂识别；主要操作以朱红印章色收束。

界面保持紧凑、清楚的桌面操作密度。地图提供地理上下文，左右信息栏保留省份和钱粮线索，中央承载当前会话或全国面板。全部中文界面共用本地 CourtSans 字体，依靠字号、字重和明暗区分层级。

**Key Characteristics:**
- 深蓝顶部与等宽侧栏、暖纸面会话、黄铜细线及朱红主操作。
- 固定比例中央窗口与独立的边缘栏位；宽屏增加地图留白。
- 圆形人物画像、纵向联系人和环形群像；官员消息在左、君主消息在右。
- 地图四个稳定底色表示政区身份；钱粮、灾情及未知状态用真实来源和文字表达。

当前视觉权威为 [Kimi v4 两京十三省 HUD](https://raft-artifacts.com/p/solidyang/simu-fifteen-provinces-hud-reference/v/4)。变量与组件以 `web/styles.css`、`web/App.tsx` 和实际组件为准；本文件 frontmatter 保存复用 token，`.impeccable/design.json` 保存渐变、阴影、动效及独立预览片段。

## Colors

深蓝与黄铜建立外框，暖纸与深褐墨色承载阅读，四种低饱和矿物色连接地图与省份列表。

### Primary
- **黄铜与亮金**（`brass`、`bright`）：描边、选中状态、图标、焦点轮廓和短角饰；不作为大面积内容底色。
- **朱红印章**（`red`、`action-top`、`action-bottom`）：主操作、降旨及事件提示。主按钮使用从上至下的朱红渐变；hover 提亮，disabled 降低不透明度与饱和度。

### Secondary
- **纸面墨色**（`ink`、`paper-title`、`paper-muted`）：正文、标题与元信息。官员气泡使用 `paper-card`，君主气泡沿用深蓝底与浅字。

### Tertiary
- **政区矿物色**（`province-gold`、`province-sage`、`province-clay`、`province-slate`）：十五地的稳定身份底色，同步用于右侧圆点与全国表格。相邻政区使用不同底色；来源映射保留在 `web/map-data.ts`。
- **水域蓝**（`map-ocean`）：舆图海面及地形边缘融合；水系、地形与政区薄层共同保留地理细节。

### Neutral
- **深蓝框架**（`panel`、`panel-low`、`panel-deep`）：顶部、两侧、全国面板的渐变与较深容器。
- **浅字层级**（`text`、`muted`、`faint`）：深蓝上的主信息、辅助信息和弱提示；黄铜透明线（`line`、`line-soft`）组织内容。
- **暖纸材质**（`paper`、`paper-low`、`paper-card`）：中央会话和对话框的渐变底、官员气泡。纸面分割线与外框使用 `paper-line`、`paper-border`。

**The Material Rule.** 深蓝承载全局框架与全国政务，暖纸面承载会话和对话框；同一窗口内用对应材质的文字、分割线和输入控件。

**The Geography Rule.** 四个政区底色保持稳定，不随钱粮、灾情或调试状态改换省份身份色。

## Typography

**Display Font / Body Font:** `CourtSans, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif`。CourtSans 对应本地 `/assets/NotoSansSC-ui.woff2`，以 `@font-face` 声明可变字重（100–900）和 `font-display: swap`。标题、正文、地图和数字使用同一字体；资源数字使用 `tabular-nums`。

### Hierarchy
- **Display**：顶部资源值（18px、650）；作为紧凑 HUD 内最强数字信息。
- **Headline**：纸面对话框标题（17px、650）。
- **Title**：侧栏标题（16px、650）；全国标题（16.5px）、中央会话标题（15.5px）使用相近层级。
- **Body**：页面正文（14px、1.65）；奏报说明使用更紧凑正文（13px、1.75），会话气泡使用 conversation token（13.5px、1.7）。
- **Label**：资源说明、身份和会话元信息（11–12px）；表格和钱粮列表使用紧凑数字层级（11–12.5px）。
- **Cartography**：SVG 标注使用同一 sans 字体、纸色描边与 `paint-order: stroke fill`；主省名字重较强，冻结省名较小较淡，地图缩放通过 SVG viewBox 与标注缩放控制。

**The Local Type Rule.** 中文标题、正文、数字和地图标注均使用已随应用提供的 CourtSans，不另引入宋体标题体系。

## Layout

这是桌面 HUD。外壳和地图占满视口并禁止页面级滚动；内容在侧栏、联系人、消息流、全国面板和对话框内部滚动。

- **外缘与网格**：外缘（24px）、网格最小间距（16px），左右栏各宽（224px）。工作区垂直居中；顶部资源栏和右侧日期阶段栏各高（54px），底部图层和恢复密谈入口高（42px）。
- **中央尺寸**：聊天与全国面板均为 4:3，最大（880×660px）。工作区高度取 `min(660px, calc(100vh - 200px), calc((100vw - 528px) * 0.75))`，中央通过高度与比例计算宽度。
- **桌面目标**：1280×800 对应中央（752×564px）；1440×900、1920×1080、3840×2160 对应中央（880×660px）。左右栏继续贴外缘，宽屏中间留下更多地图。
- **中央内部**：聊天左侧联系人列（224px），右侧为会话；标题条高（56px），消息流和输入区独立。全国入口使用同一中央槽位，保留左侧省份面板和右侧简况。
- **内容节奏**：侧栏横向内边距（16px），全国正文（16px 20px 22px），消息区（18px 22px），纸面对话框正文（18px 20px）。
- **视口策略**：当前没有窄屏重排断点。此系统的确认范围是上述桌面宽度；不要从旧规范恢复手机单列布局。

**The Fixed Center Rule.** 中央窗口始终保持 4:3；宽屏只增加地图留白，不把中央窗口拉伸为流式大面板。

## Elevation & Depth

地图为底层；深蓝和纸面窗体通过柔和外阴影、细边框和内侧高光形成浮层。短角饰只出现在窗体的左上和右下，不扩展为复杂画框。主按钮略有印章般厚度；地图选区使用亮金描边和柔光。

### Shadow Vocabulary
- **框架浮起**：深蓝窗体使用 `--lift`，并带一条浅色内高光。
- **纸面会话**：中央会话使用较宽的下投影与浅内高光，使阅读面浮于地图。
- **受保护对话框**：纸面窗体使用更深外投影，背景遮罩为深蓝半透明；固定层级覆盖 HUD。hover 履历只展示信息，点击后的履历才具有可操作对话框行为。

完整阴影值、层级语义和动效写入 sidecar。中央会话入场使用（180ms）轻微上移与淡入；普通状态切换使用（150ms）。`prefers-reduced-motion: reduce` 关闭过渡与入场动画。

## Shapes

窗体使用圆润但克制的角（panel 14px、dialog 16px）；控件以紧凑圆角（6–10px）分层。联系人卡片使用 contact 圆角（11px），头像始终为圆形。群像把最多四个小头像沿圆环排列；不改为方形拼贴。官员与君主气泡用相对的小尖角（3px）标出说话方向，其余角（14px）。

## Components

### Buttons

朱红主操作用于截奏、下发、降旨及明确的人物任免操作，使用黄铜边框和浅字。深蓝次按钮使用弱黄铜填充；hover 增强边框和亮金文字。纸面工具按钮使用半透明浅底和褐色文字。全局键盘焦点使用亮金轮廓（2px、offset 2px）；disabled 保留原有尺寸并降低透明度。中央降旨按钮使用较高的纵向内边距，保持与输入区对齐。

### Chips

纸面传召芯片显示真实群成员；选中时加强黄铜填充、边框和字重。地图图层使用深蓝底部容器和黄铜内描边选中态。省份身份点始终为四种稳定底色；状态文字负责表达事实。

### Cards / Containers

顶部与侧栏是深蓝渐变容器；左侧省份、右侧十五地简况高度与中央工作区一致。全国面板沿用深蓝容器，摘要卡与表格用细线组织。中央聊天与事件、人物、候选人、成员、机务及凭据对话框使用纸面材质。每种材质内部都使用对应的文字和分割线，避免把深色表单样式带入纸面。

### Inputs / Fields

会话 textarea 为浅透明纸底、褐线、深褐字；grant 数字输入在深蓝省份面板为深底，在事件纸面为浅底。纸面下拉、凭据与设置输入同样使用深字。核拨输入和全额、拒批按钮在省份与事件中指向同一份草稿，不通过外观制造第二个提交过程。

### Navigation

顶部图标入口打开中央太仓钱粮、户口灾情、百官、起居注面板；机务打开纸面对话框。省份内采用奏报 / 批复两项文字标签，选中项有亮金字与黄铜下划线。左右栏可独立收起；中央全国面板可关闭以恢复密谈。底部独立保留灾情、存银、存粮切换及御前密谈入口。

### Portraits & Conversations

个人联系人纵向排列，使用实际人物姓名、官职、圆形画像。群联系人使用环形群像及实际成员。官员气泡左对齐且用纸卡底；君主气泡右对齐且用深蓝底，圆形君主章在右侧。来源轮次、迟达、点名和传召回执是细小辅助信息，正文保持主要阅读层级。

### Province, Events & People

右侧十五地简况每行保留省名、身份色点、银与粮；未知显示未奏报或短横线，冻结地区不填演示金额。全国表格沿用相同来源。人物卡只展示真实生平、政务专长和任职记录；任命、调任、免职遵循当前开放轮次与现有接口。历史卡保留当轮任职并禁用修改。普通 ARCHIVED 历史为归档；仅实际当前第四轮 ARCHIVED 显示终局。

## Do's and Don'ts

### Do:
- Do 保持顶部和两侧的深蓝框架、中央会话及对话框的暖纸面材质。
- Do 使用本地 CourtSans、对齐的数字和可追溯的奏报来源。
- Do 保持中央 4:3、两侧等宽、边缘留白与独立滚动区。
- Do 在纸面与深蓝面板分别使用对应的文字、线条和输入控件配色。
- Do 让地图政区、全国表格和右侧列表共用同一套四个身份底色。
- Do 清楚区分未奏报、冻结疆域、历史旧档与实际四轮终局。

### Don't:
- Don't 恢复旧的全浅色面板、宋体标题或把灾情等级当作政区身份底色。
- Don't 在宽屏拉大中央窗口，或把桌面设计扩展为未经确认的移动端布局。
- Don't 将原型演示的人物、属性评分或钱粮数值写成真实游戏数据。
- Don't 用零值代替未知数值，或用终局标记普通历史归档。
- Don't 让全国面板替换左侧省份栏，或将联系人改为横向标签导航。
