# 订单详情、物流跟踪与运费估算（Order Details, Tracking and Shipping Estimate）

面向澳洲药房业务场景的全栈订单管理系统：读取本地 JSON 订单数据，匹配 `product_list` 商品资料，
完成 GST 计算、运费估算，并展示 Australia Post / StarTrack 与 TNT 的物流跟踪状态。

- 前端：Vue 3 + Vite（`frontend/`）
- 后端：Python + FastAPI（`backend/`）
- 数据：`data/` 目录下的 JSON 文件（本版本不使用数据库）
- 启动：**一条 Python 命令启动整个项目**（`python run.py`）

---

## 1. 快速开始

```bash
# 1) 安装 Python 依赖（首次运行 run.py 也会自动安装缺失的包）
pip install -r requirements.txt

# 2) 准备环境变量：复制模板并填入测试凭证
cp .env.example .env        # Windows: copy .env.example .env

# 3) 一条命令启动（首次会自动 npm install + 构建前端，然后启动 Web 服务）
python run.py
```

打开 <http://127.0.0.1:8000>，接口文档在 <http://127.0.0.1:8000/docs>。

### 可用的启动参数

| 命令 | 作用 |
| --- | --- |
| `python run.py` | 若 `frontend/dist` 不存在/已过期则构建，然后由一个 FastAPI 进程同时提供 `/api` 与静态页面 |
| `python run.py --dev` | 前端 Vite 开发服务器（:5173，带 HMR）+ 后端自动重载（:8000），Vite 代理 `/api` |
| `python run.py --rebuild` | 强制重新执行 `npm run build` |
| `python run.py --no-build` | 直接使用已有的 `frontend/dist` |
| `python run.py --build-only` | 只构建前端后退出（CI / 只想验证构建时用） |
| `python run.py --port 9000 --open` | 指定端口并自动打开浏览器 |

> Node.js 只作为前端构建工具（需要 18+），运行时完全由 Python 驱动。

---

## 2. 目录结构

```
AU/
├── run.py                      # 一键启动入口（依赖检查 / 前端构建 / uvicorn）
├── requirements.txt
├── .env.example                # 只有变量名，可安全提交
├── .gitignore                  # 排除 .env、node_modules、dist、缓存
├── backend/
│   └── app/
│       ├── main.py             # FastAPI 应用：API 路由 + 静态资源 + SPA fallback
│       ├── config.py           # 从环境变量读取配置（凭证只在服务端）
│       ├── data_store.py       # JSON 数据加载（按 mtime 缓存，改文件不用重启）
│       ├── routers/
│       │   ├── orders.py       # 订单列表 / 详情 / 物流跟踪
│       │   ├── products.py     # product_list 查询
│       │   └── meta.py         # /api/health（只暴露配置状态，不暴露凭证）
│       └── services/
│           ├── measures.py     # "10.0mm"/"0.2g"/"1000.0mm³" 等度量解析
│           ├── pricing.py      # Decimal + ROUND_HALF_UP 的 GST 计算
│           ├── shipping.py     # 运费估算公式
│           ├── tracking.py     # Australia Post 实时查询 + TNT 未实现状态
│           └── orders.py       # 订单装配：SKU 匹配、分组、汇总
├── data/
│   ├── orders.json             # 订单（含 2 个题目订单 + 3 个自建测试订单）
│   ├── products.json           # product_list（10 条查询导出 + 9 条占位记录）
│   ├── shipments.json          # Assigned Tracking → 运单号 / 承运商映射
│   └── shipping_rates.json     # 运费规则参数（全部可配置）
├── frontend/
│   ├── src/App.vue             # 页面组装、数据加载、状态管理
│   ├── src/components/         # 订单列表 / 订单头 / 明细表 / 金额汇总 / 跟踪面板 / 占位图
│   ├── src/api/client.js       # fetch 封装（超时、错误归一）
│   └── src/utils/format.js     # 金额、日期、状态徽章格式化
└── tests/                      # pytest：计算、运费、订单装配、API、SPA、前端构建
```

---

## 3. 输入数据结构

### 3.1 `data/orders.json`

```jsonc
{
  "orders": [
    {
      "order_no": "PO-20251130-00072",
      "order_date": "2025-11-30",          // 也兼容 "30/11/25"
      "status": "Completed",
      "company": "V22 Dispensary",
      "customer": { "name": "...", "phone": "...", "email": "..." },
      "shipping_address": {
        "line1": "125 Toorak Road",
        "suburb": "South Yarra",
        "state": "VIC",
        "postcode": "3141",
        "country": "AU"
      },
      "items": [
        { "sku": "TBAMET10", "quantity": 3, "tracking_ref": "Track 1" }
      ]
    }
  ]
}
```

`quantity` 允许是整数、浮点或数字字符串；`tracking_ref` 对应 `shipments.json` 中的分配标识。

### 3.2 `data/products.json`

来自题目 SQL 查询网站导出的 `product_list` 结构（`SKU`、`ProductName`、`RRP`、`Size`、`weight`、
`length`、`width`、`height`、`volume`、`Description` 等）。额外增加一个 `data_source` 字段：

- `query_export`：从题目提供的 SQL 查询工具导出、原样保留的 10 条真实数据
  （导出文件位于题目资料包中，未随本仓库提交）；
- `generated_placeholder`：本地生成的占位记录（原因见第 7.1 节）。

### 3.3 `data/shipments.json`

```jsonc
{ "tracking_ref": "Track 1", "tracking_no": "2FWZ50008569",
  "carrier_name": "StarTrack / Australia Post", "provider": "auspost", "test_data": false }
```

`provider` 决定使用哪个物流集成：`auspost`（已实现）或 `tnt`（未实现，见第 7.2 节）。

### 3.4 `data/shipping_rates.json`

运费公式的**全部常量**，包括基础运费、包含重量、续重单价、包装重量、体积重除数、
跨州/偏远附加费、`Size` 的可信区间等。改这里即可调整运费，无需改代码。

> 业务代码中没有任何订单号、SKU、价格或金额被硬编码，全部来自上述 JSON。

---

## 4. 计算规则（第 4 节）

| 项目 | 公式 |
| --- | --- |
| Ex-GST 单价 | `RRP / 1.10` |
| 行小计（ex GST） | `Ex-GST 单价 × 数量` |
| 订单小计（ex GST） | 该订单所有行小计之和 |
| GST | `订单小计 × 10%` |
| 订单总额 | `小计 + GST + 运费` |
| 币种 | AUD，统一两位小数 |

实现要点：

- 全程使用 `Decimal` + `ROUND_HALF_UP`，金额量化到分，保证「界面上显示的数字能对上」；
- 先把 RRP 换算成两位小数的 ex-GST 单价，再乘数量（`120.00 / 1.1 = 109.09`，×2 = `218.18`），
  这样明细行展示的 `单价 × 数量 = 小计` 在视觉与数值上都成立；
- GST 只对订单小计计算，运费按 ex-GST 处理（见第 7.4 节假设）。

---

## 5. 运费估算（第 7 节，bonus 部分已实现）

### 5.1 方案选择

题目允许「使用物流 API」或「基于重量与体积的合理公式」。Australia Post 的定价 API 需要
额外的账户与包裹申报信息，而题目提供的 testbed 只用于 tracking，没有可用的定价响应，
因此本项目采用**可解释、可配置的公式估算**，并在页面上展示每一组成分。

### 5.2 公式

```
单件净含量   = max(weight 字段, Size 值)            # Size 仅在可信区间内才采信
单件实际重量 = 单件净含量 + 包装配重(40g)            # 克
单件体积重   = 长 × 宽 × 高 ÷ 5000                  # cm³ → kg
单件计费重量 = max(实际重量, 体积重, 0.05kg)
分组计费重量 = Σ(单件计费重量 × 数量)，最低 0.5kg
分组运费     = 基础运费 8.95（含前 5kg）+ 续重(每满 1kg 向上取整 × 1.10)
              + 跨州附加费 4.55（收件州 ≠ 发货州）+ 偏远邮区附加费 6.50
订单运费     = 该订单每个 tracking 分组运费之和
```

发货地为 `2111 Ryde NSW`，收件邮区取自订单地址。

### 5.3 粒度与边界

- 运费按**订单级**汇总，但按订单内的 tracking 分组分别计算后相加，这样可以准确表达
  「同一订单拆分多个包裹」以及「某个承运商未实现」的情况；
- **没有任何可计价行的分组不会产生费用**（例如 SKU 未匹配或数量非法），显示 A$0.00 并说明原因，
  绝不凭空生成运费；
- `product_list` 的 `Size` 是无单位字段，真实数据中既有 `10`（10g 花）也有 `1350`（多支装），
  因此只有落在 `net_content_min_g ~ net_content_max_g`（默认 1–200）区间内才被当作净含量，
  否则只使用 `weight` 字段 + 包装配重 + 体积重，避免运费被放大一个数量级；
- 收件州缺失时**不**加收跨州附加费（不做猜测）。

---

## 6. 物流跟踪（第 6 节）

### 6.1 Australia Post / StarTrack（已实现）

- 端点：`{AUSPOST_API_BASE}/track?tracking_ids=<运单号>`，默认指向题目提供的 testbed；
- 认证：实测 **HTTP Basic Auth**（用户名 = Key，密码 = Password）可用；
  `AUTH-KEY` 请求头在 testbed 上返回 `401 API_001`，因此实现里采用 Basic Auth；
- 题目第 11 节提示「Australia Post API 目前存在权限问题」。本环境实测：**用 Basic Auth 调用
  `/track` 返回 200 并带回真实结构的事件数据**，权限问题未复现；若在其他网络/账号下确实失败，
  页面会按 6.3 的降级规则显示对应的 401/超时/错误说明，而不是留空或伪造结果；
- 展示：当前状态（`consignment.status` / `trackable_items[].status`）、最后更新时间与地点、
  事件时间线（默认 4 条，可展开全部）、子包裹（article）数量；
- 缓存：默认 120 秒内存缓存，页面上的「Refresh tracking」会带 `?refresh=true` 强制重查；
- 并发：同一订单的多个运单并行查询，单个失败不影响其它。

### 6.2 TNT（未实现，按题目要求显示为不可用）

TNT 在题目中是 **bonus**。经研究，TNT 的 Rated Transit Times（RTT）使用 XML 报文 + Secured
Weblinking 认证，需要真实的 UAT 账号、账号级协议与报文结构对接，本提交**未实现**，因此：

- Track 3 / Track 6 的跟踪状态固定为 `not_implemented`，页面上明确说明原因，不伪造任何物流事件；
- 与 TNT 相关的运费按题目要求显示 **A$0.00**（`data/shipping_rates.json` 中 `provider_rules.tnt.fee_aud = 0`）。

### 6.3 失败与降级

跟踪接口永远不会让页面崩溃，状态分为：`available` / `unavailable` / `not_implemented` / `error`。
以下情况都会被转换成可读的说明文字：

| 情况 | 表现 |
| --- | --- |
| 未配置凭证 | 「credentials are not configured...」，提示去 `.env` 配置 |
| `ENABLE_LIVE_TRACKING=false` | 「Live tracking is disabled」 |
| HTTP 401 | 「Australia Post rejected the credentials (HTTP 401)...」 |
| HTTP 4xx/5xx | 显示状态码与 API 返回的错误描述 |
| 超时（默认 8s） | 「Australia Post API timed out」 |
| 网络异常 / 非 JSON 响应 | 明确报错，不抛出 500 |

---

## 7. 遇到的难点与处理方式

### 7.1 题目 SKU 资料无法从查询网站取得

- 现象：题目给出的 SQL-like 查询网站（`script.google.com`）在本机构建环境中无法访问（连接超时），
  而题目资料包提供的 `product_list` 导出只有 10 条记录，且**完全不包含订单中的 9 个 SKU**
  （`TBAMET10`、`AURPUR10`、`HARNIG`…）。
- 处理：保留 10 条真实导出数据不动，另外按 `product_list` **完全相同的字段结构**生成 9 条占位产品记录，
  逐条标记 `"data_source": "generated_placeholder"`，页面上以 `Placeholder record` 标签明示。
- 影响与替换方式：替换为真实数据只需把查询结果导出成同样字段的 JSON 覆盖 `data/products.json` 的
  `rows`（或修改对应行的 `RRP`/`weight`/尺寸），业务代码与页面无需任何改动。

### 7.2 testbed 不校验运单号真实性

- 现象：Australia Post testbed 对**任意格式合法**的单号（例如 `INVALID12345`、`2FWZ00000000`）
  都返回同一份 mock 事件；只有格式非法（如 `ABC-999`）才返回 `400`。
- 处理：README 如实记录该限制；程序按 API 实际返回展示，不额外伪造或推测状态；
  同时保留真实单号的 API 错误路径（401/400/超时）为可展示的降级状态。
- 另外观察到 Track 3 的 TNT 单号 `305506914` 在 AusPost testbed 上也能查到（被当作 Parcel Post 返回数据）。
  按题目要求「为每个运单号使用合适的承运商」，该单仍归属 TNT 并显示 `not_implemented`，
  不把 AusPost 的返回当作 TNT 结果，以免误导。

### 7.3 商品度量字段不规整

- `weight` 记录的是包装单位重量（0.1–1.0g），而 `Size` 才是净含量（10g 花 / 30mL 油），
  但 `Size` 同时存在 `1350` 这类多支装数值；
- 处理：见 5.3 的可信区间策略；`measures.py` 对带单位的字符串做宽容解析（`mm/cm/m`、`mg/g/kg`、
  `mm³/cm³/mL/L`），无法解析时返回 `None` 而不抛异常。

### 7.4 金额一致性与税务处理假设

- 所有金额用 `Decimal` 计算并量化到分，避免浮点误差导致「小计相加 ≠ 合计」；
- 题目定义 `Total = Subtotal + GST + Shipment Fee` 且 `GST = Subtotal × 10%`，即 GST 只作用于商品小计，
  因此运费按 ex-GST 金额计入总额（不重复计税）。该假设记录在
  `data/shipping_rates.json` 的 `gst_treatment` 字段，并随 API 返回。

### 7.5 真实订单的健壮性

- SKU 大小写/空格、数量为 0/负数/非数字/浮点、订单引用未登记的 tracking 编号、
  同一订单多个包裹、承运商未实现——都只会影响**对应的行或包裹**，其余部分照常计算；
- 校验失败的行会以红色高亮并给出具体原因，同时出现在页面顶部的提示区，
  且**不计入**小计/GST/总额（不会静默按 0 元处理）。

---

## 8. 自建测试订单（第 8 节）

除题目提供的 2 个订单外，`data/orders.json` 另含 3 个测试订单，用于演示边界情况：

| 订单号 | 目的 |
| --- | --- |
| `PO-20251205-00088` | 含一个 `product_list` 中不存在的 SKU（`SKU-NOT-IN-CATALOGUE`），演示未匹配处理 |
| `PO-20251208-00091` | 含非法数量（`0` 与 `-2`），演示逐行校验，其余行照常计价 |
| `PO-20251210-00095` | 走 TNT（Track 6），演示「承运商未实现」与运费 A$0.00 |

这些订单的客户姓名/地址/运单号均为测试数据（`shipments.json` 中以 `test_data: true` 标记）。

---

## 9. API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 数据文件状态、承运商配置状态（不含凭证内容）、运费信息 |
| GET | `/api/orders` | 订单列表（含金额汇总，不含跟踪，保证首屏快） |
| GET | `/api/orders/{order_no}` | 订单详情：明细行、GST 拆分、运费分组、警告、跟踪分组 |
| GET | `/api/orders/{order_no}/tracking?refresh=true` | 实时物流状态（可强制刷新） |
| GET | `/api/products?search=` | `product_list` 查询（按 SKU/名称模糊匹配） |
| GET | `/api/products/{sku}` | 单个商品 |

页面加载顺序：先渲染订单与金额，再异步请求跟踪状态，跟踪慢或失败都不会阻塞金额展示。

---

## 10. 测试

```bash
python -m pytest tests -q                       # 49 passed, 2 skipped（离线；跳过联网与前端构建用例）

# 可选：真实调用 Australia Post testbed
RUN_LIVE_TRACKING_TEST=1 python -m pytest tests/test_api.py::test_live_auspost_tracking -q

# 可选：完整跑一次前端 npm install + vite build
RUN_FRONTEND_BUILD=1 python -m pytest tests/test_frontend_build.py -q
```

覆盖范围：

- `tests/test_pricing.py`：GST 换算、两位小数四舍五入、零值/非法值；
- `tests/test_shipping.py`：基础运费、跨州/偏远附加费、体积重、续重、TNT 归零、分组求和、按订单计算；
- `tests/test_orders.py`：题目两个订单的逐行金额与总额（订单 1 = A$2,136.50；订单 2 = A$2,774.50）、
  缺失 SKU、非法数量、不可用承运商、日期格式、以及「用目录中任意 SKU 组合的新订单」；
- `tests/test_regressions.py`：全无效订单不产生运费、空分组归零、tracking 编号大小写/空格归并、
  `Size=1350` 不被当作克数、收件州缺失不加跨州费；
- `tests/test_api.py`：接口契约、404、凭证不回显、跟踪降级、TNT `not_implemented`；
- `tests/test_spa.py`：构建产物由 FastAPI 提供、SPA 路由回落到 `index.html`、`/api/*` 不被吞掉。

---

## 11. 凭证与安全

- 所有凭证只从**服务端环境变量**读取（`.env`），前端只访问同源的 `/api`，浏览器中不含任何 key；
- `.env` 已在 `.gitignore` 中排除；`.env.example` 只保留变量名与说明；
- `.gitignore` 同时排除 `node_modules/`、`frontend/dist/`、缓存与日志；
- `/api/health` 只返回「是否已配置」，绝不回显凭证值；
- 测试用例 `test_health_reports_data_files_and_courier_state` 会断言响应体中不出现 API key。

## 12. 假设清单

1. RRP 为含 GST 的 SKU 价格，AUD 计价（题目已确认）。
2. GST 仅对商品小计计算，运费按 ex-GST 计入总额。
3. `Size` 字段在 1–200 区间内视为单件净含量（g 或 mL），否则忽略。
4. 包装配重 40g/件、体积重除数 5000、基础运费 8.95、跨州 4.55、偏远 6.50 等均为可配置估算参数，
   参考 Australia Post eParcel 的常见档位，不代表真实报价。
5. 运费按订单内 tracking 分组分别估算后求和；TNT 分组记 A$0.00。
6. 商品图片使用中性的药剂瓶占位图并标注 `Product N`（题目明确允许）。
7. `product_list` 中缺失的 9 个订单 SKU 使用占位产品记录（见 7.1）。
8. 自建测试订单及其运单号仅为演示数据。
