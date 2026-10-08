# justdowork-proxy（中文文档）

[English](README.md) · **简体中文**

让 **Claude Code** 跑在一个"不那么标准"的 OpenAI/Anthropic 兼容中转站上。

本项目最初针对的中转站是 `https://api.justwoker.icu`，但它修复的问题很普遍：
丢工具调用、无视 `tools` 数组、流式响应残缺、随机返回空 `403` 的中转站都适用。

**你把 Claude Code 指向本代理，而不是指向中转站。** 代理双向翻译、修复模型
输出的 JSON、自己执行网络搜索，最终交给 Claude Code 一条干净、符合标准的流。

> **许可证：** 个人、业余、教育、研究、非营利与政府用途免费；**商业用途——
> 包括转售或将其作为付费服务托管——需要另行书面授权。** 见
> [许可证](#许可证)。

---

## 关于本 fork 与 `docker` 分支

本仓库是 [RavenHogWarts/justdowork-proxy](https://github.com/RavenHogWarts/justdowork-proxy)，
fork 自 [abdurrehmandaudi/justdowork-proxy](https://github.com/abdurrehmandaudi/justdowork-proxy)。
fork 的默认分支是 **`docker`**：它承载上游的全部代码——包括 **v3.0.0** 的
改进（更智能的历史裁剪、自适应扩展思考、并发网络工具）——并在此基础上增加了：

| 新增内容 | 带来的能力 |
|---|---|
| Docker 打包 | 任何装有 Docker 的机器上 `docker compose up -d --build` 即可；每次打 `v*` 标签自动发布 amd64 + arm64 双架构镜像到 GHCR |
| `client_key_passthrough`（默认开启） | 上游调用**优先使用客户端请求带来的密钥**，cc-switch 继续统一管理供应商密钥；可选的后备密钥在 401/403 时自动接管 |
| Dashboard 密钥面板 | 在浏览器里保存/更换后备密钥——立即生效、无需重启、容器重建后仍保留 |
| 访问令牌（`CCPROXY_TOKEN`） | 端口暴露给回环地址以外时可选的鉴权手段 |
| 双语 dashboard | 英文 / 简体中文界面，按浏览器记忆选择，`UI_LANG` 设默认语言 |
| 对卷友好的运行时数据 | 保存的密钥、日志、转储集中在同一个 `CCPROXY_DATA_DIR` |
| CI | 每次 push 自动跑两套测试并验证 Dockerfile 可构建 |

对上游文件的改动刻意保持最小（`ccproxy.py` 中的 `LISTEN_HOST` 环境变量覆盖、
`.env` 加载、客户端密钥透传与密钥管理接口，`dashboard.py` 中的密钥面板）；
其余均为新增文件。`main` 分支保持与上游完全一致。

**Docker 深入文档：** [DOCKER.zh-CN.md](DOCKER.zh-CN.md) · [DOCKER.md](DOCKER.md)（英文）

---

## 它修复了什么

| 中转站的问题 | 代理的做法 |
|---|---|
| 只认字面名为 `read`/`write`/`edit`/`bash` 的工具 | 这四个以真实 schema 原生下发；其余工具走 `<tool_call>` 文本协议 |
| 模型写出的 JSON 带字面换行和非法转义，调用被丢弃 | 四步修复：严格解析 → 控制字符 → 转义修复 → 括号配平 |
| 流式响应丢文本和工具块（只剩思考增量） | 代理自行合成 SSE 流，每 3 秒一个 ping，不会超时 |
| 无法执行 `WebSearch` / `WebFetch` | 代理自己去搜 DuckDuckGo / 打开网页，循环到模型给出回答；一条回复里的多个搜索并发执行 |
| 巨大的历史导致 524 超时 | 把对话装进字符预算——并为**用户本人的发言**保留预留份额 |
| 模型几轮之后"忘了"任务 | 从不静默丢弃历史：裁剪处留下标记，并在系统提示里给出 `Context notice`，模型会说"我丢了那段"而不是瞎猜 |
| 模型编辑一个没看到结尾的文件 | 工具输出不再被截到 4000 字符——大的 `Read` 最大可完整送达（`max_tool_result_chars` = `32000`） |
| 约 26% 的请求随机返回空 `403`/`503` | **立即**重试（实测中转站拒绝并无冷却期，0 秒后重试即返回 200）；`403` 视为可重试 |
| 支持思考但从不请求 | 自适应扩展思考：预算只给**做规划**的那一轮（新的用户消息）；执行轮保持快速 |
| 每个请求虚增约 10.4k 输入 token | `usage_baseline_tokens` 修正上报数字（真实成本仍在——那是中转站的事） |

---

## 快速开始：Docker

不需要 Python、不需要配置文件，而且得益于客户端密钥透传，**启动时连密钥都
不需要**：

```sh
# 1. 获取代码（docker 分支只存在于本 fork）
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker

# 2. 构建并启动
docker compose up -d --build
```

首次构建约需 1～2 分钟，之后启动只需数秒。代理默认发布在
**<http://127.0.0.1:18181>**（默认只绑宿主机回环地址）。

验证：

```sh
curl http://127.0.0.1:18181/health
# {"ok": true, ..., "key_set": false, "client_key_passthrough": true}
```

`key_set: false` 是正常的——还没有配置后备密钥。放入密钥的三种方式（可组合）：

1. **cc-switch 模式（推荐）**：把真实中转站密钥填进
   [cc-switch](https://github.com/farion1231/cc-switch) 的供应商配置；Claude
   Code 每次请求自动带上，代理直接用它调上游。
2. **Dashboard 面板**：打开 <http://127.0.0.1:18181/>，页面底部 **API key**
   面板保存一个密钥；立即生效并自动持久化。
3. **环境变量**：首次启动前用 `.env` 预置后备密钥
   （见 [DOCKER.zh-CN.md](DOCKER.zh-CN.md#六可选的-env)）。

不想克隆仓库的话，直接用发布好的镜像（CI 每次打 `v*` 标签都会构建
amd64 + arm64）：

```sh
docker run -d --name justdowork-proxy --restart unless-stopped \
  -p 127.0.0.1:18181:8181 ghcr.io/ravenhogwarts/justdowork-proxy
```

然后按[把 Claude Code 接上来](#把-claude-code-接上来)一节连接。端口、数据卷、
自定义 `config.json`、Windows 数据放其他盘、访问令牌等，全部见
[DOCKER.zh-CN.md](DOCKER.zh-CN.md)。

---

## 快速开始：本地 Python 运行

不用 Docker 也行——总共只有两个纯 Python 依赖，装进本地 `.venv`。

**前置条件：** [Python 3.9+](https://www.python.org/downloads/) 和中转站的
API 密钥。Windows 安装时在第一屏勾选 *Add python.exe to PATH*。

```sh
# macOS / Linux
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker
export UPSTREAM_API_KEY='sk-...'
sh start.sh          # 首次运行会创建 .venv 并安装 flask + requests
```

```bat
:: Windows（命令提示符 / PowerShell）
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker
setx UPSTREAM_API_KEY "sk-..."    :: 只对之后新开的终端生效
start.bat
```

代理启动在 `http://127.0.0.1:8181`（本地运行的默认端口；Docker 部署发布的是
18181）。保持它运行；密钥问题见[获取 API 密钥](#获取-api-密钥)。

---

## 获取 API 密钥

这里的密钥是**中转站的**密钥，不是 Anthropic 的。以本项目针对的中转站为例，
在 [api.justwoker.icu](https://api.justwoker.icu) 注册，从控制台复制 `sk-...`
密钥。

放哪儿，按方便程度排序：

| 位置 | 说明 |
|---|---|
| cc-switch 供应商配置 | 密钥随每个请求到达（`client_key_passthrough`）；代理侧不存任何密钥 |
| Dashboard 的 **API key** 面板 | 保存为后备密钥；立即生效、自动持久化（Docker 卷或本地 `.env`） |
| `UPSTREAM_API_KEY` 环境变量 | `export`，Windows 用 `setx`（只对新终端生效） |
| `config.json` → `"api_key"` | 也可以——但**切勿提交到仓库**；仓库内置版本为 `""` |

代理内优先级：真实环境变量 > `.env` > `config.json`。完全不设后备密钥时，
代理以客户端密钥模式运行，依赖客户端带来的密钥；上游返回 401/403 时若存在
后备密钥则自动改用它重试一次。请求日志会标注来源（`key=client` /
`key=config`）。

---

## 验证是否正常

用浏览器打开 **<http://127.0.0.1:18181/>**（Docker）或
**<http://127.0.0.1:8181/>**（本地运行），会看到实时 dashboard：请求量、
输入/输出 token、中转站的虚增 token、工具调用、被丢弃的调用、重试，以及每个
请求的柱状图，每 2 秒刷新一次。

`/health` 是机器可读的检查：

```json
{"ok": true, "upstream": "https://api.justwoker.icu", "model": "claude-opus-4-8", "key_set": true, "client_key_passthrough": true}
```

`"key_set": false` 只说明没有*后备*密钥——cc-switch 模式下这完全正常。

也可以跑离线测试套件——**不需要**任何 API 密钥，套件会启动自己的模拟上游：

```sh
sh run_tests.sh          # test_offline.py —— macOS / Linux
run-tests.bat            :: Windows
python test_branch.py    # docker 分支专属套件（需要 Python，不需要 Docker）
```

预期输出：`RESULT: 70 pass, 0 fail` 与 `RESULT: 40 pass, 0 fail`。

---

## 把 Claude Code 接上来

省事的方式——`run-claude.sh` / `run-claude.bat` 会先确认代理在应答，再通过
一次性的 `--settings` 文件把 Claude Code 指向代理（**不会**修改你的全局
`~/.claude/settings.json`），设置 `ENABLE_TOOL_SEARCH=false`，并透传其余
参数。脚本默认端口是 8181，Docker 部署下要设 `PROXY`：

```sh
PROXY=http://127.0.0.1:18181 sh run-claude.sh          # Docker
sh run-claude.sh --continue --model claude-opus-4-8    # 本地默认端口
```

手动设置：

```sh
export ANTHROPIC_BASE_URL='http://127.0.0.1:18181'   # 本地运行则是 :8181
export ANTHROPIC_API_KEY='sk-你的中转站密钥'          # 建议填真实密钥，或 dummy
export ENABLE_TOOL_SEARCH='false'
claude
```

`client_key_passthrough` 开启（默认）时，这里填的密钥就是代理发往上游的
密钥——请填**真实中转站密钥**。填 `dummy` 也可以，前提是已设置后备密钥；
上游返回 401 时会自动落到后备密钥上。

**配合 cc-switch：** 把代理加为自定义供应商（endpoint
`http://127.0.0.1:18181`，API key 填真实中转站密钥，模型随意），并在
Claude Code 全局配置的 `env` 块里一次性写上 `"ENABLE_TOOL_SEARCH": "false"`
——完整步骤见
[DOCKER.zh-CN.md](DOCKER.zh-CN.md#四与-cc-switch-配合使用)。

---

## 哪些功能可用

| 功能 | 实现方式 |
|---|---|
| `Read` `Write` `Edit` `Bash` | 中转站的**原生**工具（`read`/`write`/`edit`/`bash`） |
| `Agent`（子代理、并行）、`Monitor`、`Task*`、`TodoWrite`、MCP 工具 | `<tool_call>` 文本协议 |
| `WebSearch` | **代理自己**搜 DuckDuckGo——一条回复要多个搜索时并发执行 |
| `WebFetch` | **代理自己**打开网页 |
| `fetch_image` | **代理自己**取图 |
| `/v1/messages/count_tokens` | 本地估算（中转站返回 404） |
| `/v1/models` | 可用 |
| 流式 | SSE + **每 3 秒一个 ping**（不留死寂、不超时） |

已用真实 Claude Code 验证：一条消息并行启动四个 `Agent` 子代理，各自执行
实时网络搜索，各自写出独立的 HTML 文件——四个文件全部落盘、格式完好且各
不相同。

---

## 配置

所有开关都在 `config.json` 的 `features` 下；环境变量优先于文件。最重要的
几个：

```jsonc
"max_history_chars": 220000,    // 历史预算，约 5.5 万 token。最大的调节杆。
"max_tool_result_chars": 32000, // 大型 bash/文件输出最多转发多少字符
"compact_tools": true,          // false = 完整工具描述（token 多得多）
"upstream_retries": 2,          // 每次重试都会重发整个载荷 = 花费 token！
"usage_baseline_tokens": 0,     // 设为 10380 可隐藏本中转站的虚增 token
"dump_requests": false,         // true = 把每个请求存到 debug_dump/（占磁盘）
```

**最大的调节杆是 `max_history_chars`。** Claude Code 每次请求都发送整个会话。
从 `220000`（约 5.5 万 token）降到 `120000`（约 3 万 token）大约省一半
费用——代价是模型记得的早期对话更少（但它会被告知哪些被裁掉了）。

环境变量（对 Docker 友好；本地运行同名生效）：

| 变量 | 覆盖项 | 说明 |
|---|---|---|
| `UPSTREAM_API_KEY` | `api_key` | 后备中转站密钥 |
| `TARGET_URL` | `upstream_base_url` | 不改文件即可切换中转站 |
| `PORT` / `LISTEN_HOST` | `listen_port` / `listen_host` | 容器内默认：`8181` / `0.0.0.0` |
| `UI_LANG` | `ui_lang` | dashboard 默认语言，`en` 或 `zh` |
| `CCPROXY_TOKEN` | `proxy_token` | 除 `/health` 外所有接口都要求 `X-Proxy-Token` / `Bearer`——端口一旦暴露给回环地址以外就应开启 |
| `CCPROXY_DATA_DIR` | — | 保存的密钥、日志、转储所在目录（镜像内为 `/app/data`） |
| `CCPROXY_SERVER` | — | 设为 `flask` 强制用开发服务器替代 waitress |

**安全默认：** 代理本身没有鉴权，因此 Docker 部署默认只绑定宿主机
`127.0.0.1`。要服务其他机器，设置 `CCPROXY_TOKEN` 和 `CCPROXY_BIND=0.0.0.0`
（配合防火墙规则）——细节见 [DOCKER.zh-CN.md](DOCKER.zh-CN.md#九安全须知)。

---

## 常见问题

**`UPSTREAM_API_KEY is not set`**
只在关闭了 `client_key_passthrough` 且任何地方都没有密钥时才会出现。设置一个
密钥（cc-switch / dashboard / 环境变量），或保持透传开启。Windows 注意
`setx` 只对**新开的**终端生效。

**`ccproxy is not answering on http://…`**
代理没在运行，或端口不对。启动它（`docker compose up -d`，或 `sh start.sh` /
`start.bat`）并保持运行。

**Claude Code 说某个工具不存在（Agent、WebSearch……）**
检查模型说的是不是中转站自带的默认工具（`read_tabular`、`system_todo_write`
等）——那些不是本次会话的工具。重启代理以重建工具前导，并开一个**全新的**
Claude Code 会话——被污染的长历史会让模型持续困惑。

**出现 `Upstream 524` 超时**
载荷太大。在 `config.json` 里调低 `max_history_chars`（例如
`220000` → `120000`），并把 `max_tool_result_chars` 设为 `2000`。

**出现 `Upstream 400`**
代理已会用精简载荷重试（system 变纯字符串、去掉 `cache_control`）。若仍然
失败，查日志——Docker 下 `docker logs justdowork-proxy`，本地运行看
`ccproxy_log.txt`。

**工具调用被丢弃**
在日志里搜 `DROP tool_call` 或 `BAD JSON tool_call`。该行的 JSON 就是需要
加入修复逻辑的案例。

**端口被占用**
Docker：`CCPROXY_PORT=28181 docker compose up -d`。本地：改 `config.json`
的 `listen_port`，运行 `run-claude.sh` / `run-claude.bat` 前设
`PROXY=http://127.0.0.1:<端口>`。

**Edit 开始丢失 `old_string`/`new_string` 参数**
中转站的原生 `edit` 坏过又修好过（最近一次于 2026-10-07 用 `edit_probe.py`
验证正常）。重新跑 `python edit_probe.py`（需要 `UPSTREAM_API_KEY`）确认；
若确实坏了，从 `native_tool_map` 里删掉 `"Edit": "edit"`，Edit 即改走文本
协议。

---

## 文件说明

| 文件 | 用途 |
|---|---|
| `ccproxy.py` | 代理本体——**要运行的就是它** |
| `dashboard.py` | `/` 处的 dashboard（由 ccproxy 导入） |
| `config.json` | 配置；环境变量与 `.env` 优先于它 |
| `Dockerfile` / `docker-compose.yml.example` / `.dockerignore` | Docker 打包 |
| `DOCKER.md` / `DOCKER.zh-CN.md` | Docker 完整说明（英文 / 中文） |
| `requirements.txt` | flask + requests |
| `start.sh` / `start.bat` | 本地启动代理（macOS/Linux · Windows） |
| `run-claude.sh` / `run-claude.bat` | 让 Claude Code 走代理（支持 `PROXY`、`MODEL` 环境变量） |
| `run_tests.sh` / `run-tests.bat` | 跑离线测试套件（test_offline.py） |
| `test_offline.py` | 上游测试套件，自带模拟上游——70 项检查 |
| `test_branch.py` | docker 分支专属套件（透传、令牌、持久化）——40 项检查 |
| `edit_probe.py` / `names_probe.py` | 探针：中转站的 `edit` 是否完好 / 哪些工具名原生存在 |
| `agent_proxy.py` | **旧版本——仅留作参考，请用 `ccproxy.py`** |
| `ccproxy_log.txt` | 实时日志（运行时创建；2 MB 轮转） |

---

## 许可证

**PolyForm Noncommercial License 1.0.0**——全文见 [LICENSE](LICENSE)。

**免费使用范围：** 个人使用、业余项目、学习、研究、实验、教学，以及慈善、
教育、公共研究、公共安全/卫生、环保和政府组织。

**未经另行书面商业授权，不得：**

* 转售、再许可或重新品牌化本软件及其修改版
* 作为托管或付费服务运营（SaaS、付费 API、托管部署）
* 嵌入商业产品
* 在营利性公司内部用于支撑产生收入的工作
* 通过广告或订阅变现

任何从你这里获得副本的人也必须收到许可条款与 `Required Notice:` 行——见
[LICENSE 的 Notices 部分](LICENSE#notices)。

**商业授权**请提 issue 或联系
[@abdurrehmandaudi](https://github.com/abdurrehmandaudi)。

本项目是**源码可得（source-available），不是开源**。源码公开是有意为之：
便于你阅读、审计，亲自确认这个坐在你和 API 密钥之间的代理没有暗藏动作。

本 fork 的 Docker 打包及相关修改由 RavenHogwarts 贡献，同样遵循 PolyForm
Noncommercial License 1.0.0；它们不改变项目许可、也不解除非商业限制。上游
版权与 `Required Notice:` 行均予保留。

---

## 备注

* 一切都在本地。本地运行时代理绑定 `127.0.0.1`；Docker 下 compose 只发布到
  宿主机回环地址。你的中转站密钥只发往你配置的中转站，不出你的机器。
* `agent_proxy.py` 是早期较简单的代理，`Read`/`Write`/`Edit`/`Bash` 可用，
  但会丢弃很多其他工具调用、也无法执行网络搜索，已被 `ccproxy.py` 取代。
* `ANTHROPIC_MODEL` 里的模型名原样透传给中转站，填你的中转站认识的模型
  字符串即可。
* Docker 下由 **waitress**（生产级 WSGI）提供服务；`CCPROXY_SERVER=flask`
  可强制回退开发服务器。本地运行自动使用 Flask 开发服务器。
