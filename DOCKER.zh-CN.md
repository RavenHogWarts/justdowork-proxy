# 在 Docker 中运行 ccproxy（中文文档）

ccproxy 是一个单进程 Python 服务，仅依赖 `flask` 和 `requests` 两个纯 Python
包，因此非常适合容器化：无需编译器、无需系统级安装、无需虚拟环境。
本文只讲 Docker 相关的内容；代理本身的功能与中转站配置请先阅读
[README](README.md)，Docker 英文文档见 [DOCKER.md](DOCKER.md)。

> Docker 支持位于本仓库的 `docker` 分支；`main` 分支保持与上游一致。
> 对上游文件的改动刻意保持最小，其余均为新增文件。

---

## 一、前置条件

| 需要                | 说明                                                                |
| ------------------- | ------------------------------------------------------------------- |
| Docker              | Docker Engine 23+（含 Compose v2.20+），或较新版本的 Docker Desktop |
| 中转站 API 密钥     | 形如 `sk-...`，在中转站的控制台获取；可以先不填，见下文               |
| （可选）Claude Code | 想通过代理使用 Claude Code 时才需要                                 |

宿主机**不需要**装 Python，也**不需要**预先创建任何配置文件——Python 在
镜像里，密钥可以由 cc-switch 带入或在网页面板里设置。

---

## 二、安装并启动

以下 4 步走完，代理就在跑了。

### 步骤 1 —— 安装 Docker（已装可跳过）

* Windows / macOS：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，装完启动它，等右下角图标显示 Docker 正在运行
* Linux：安装 Docker Engine 与 docker compose 插件（各发行版官方源均有）

验证：

```sh
docker --version
docker compose version
```

两条都有版本号输出即可。

### 步骤 2 —— 获取代码

```sh
git clone https://github.com/RavenHogWarts/justdowork-proxy.git
cd justdowork-proxy
git checkout docker          # Docker 支持只存在于本 fork 的 docker 分支
```

> 注意：`docker` 分支只在上面这个 fork 仓库里；克隆上游
> `abdurrehmandaudi/justdowork-proxy` 是切不出这个分支的。

### 步骤 3 —— 构建并启动

```sh
docker compose up -d --build
```

首次构建约需 1～2 分钟（下载基础镜像并安装依赖），之后再启动只需数秒。
代理默认发布在 **<http://127.0.0.1:18181>**（宿主机侧默认只绑回环地址）。

### 步骤 4 —— 验证并放入密钥

验证（浏览器打开 <http://127.0.0.1:18181/health> 也行）：

```sh
curl http://127.0.0.1:18181/health
# {"ok": true, ..., "key_set": false, "client_key_passthrough": true}
```

`key_set: false` 是正常的——还没有配置后备密钥。密钥三种放法，任选其一
（可组合）：

1. **cc-switch 模式（推荐）**：在 cc-switch 的供应商配置里填真实中转站
   密钥，Claude Code 每次请求自动带上，ccproxy 直接用它调上游。详见
   [四、与 cc-switch 配合使用](#四与-cc-switch-配合使用)。
2. **dashboard 面板**：打开 <http://127.0.0.1:18181/>，页面底部 **API key**
   面板保存一个密钥，立即生效并自动持久化，作为后备密钥。
3. **可选的 `.env` 文件**：见[六、可选的 .env](#六可选的-env)，适合想把
   后备密钥放进文件、且希望重建容器后也不丢的场景。

---

## 三、连接 Claude Code

代理地址是 `http://127.0.0.1:18181`（compose 默认宿主端口），两种方式任选：

**方式 A —— 用自带脚本（需指定 PROXY）**

`run-claude.sh` / `run-claude.bat` 默认连 8181，而 Docker 部署的默认端口是
18181，所以要在前面加 `PROXY` 环境变量：

```sh
PROXY=http://127.0.0.1:18181 sh run-claude.sh     # macOS / Linux / Git Bash
```
```bat
set PROXY=http://127.0.0.1:18181
run-claude.bat                                    :: Windows
```

脚本会自动把 Claude Code 指向代理，且**不会**修改你的全局
`~/.claude/settings.json`。

**方式 B —— 手动设置环境变量**

```sh
export ANTHROPIC_BASE_URL='http://127.0.0.1:18181'
export ANTHROPIC_API_KEY='sk-你的密钥'    # 或 dummy，见下
export ENABLE_TOOL_SEARCH='false'
claude
```
```bat
set ANTHROPIC_BASE_URL=http://127.0.0.1:18181
set ANTHROPIC_API_KEY=sk-你的密钥
set ENABLE_TOOL_SEARCH=false
claude
```

> 密钥来源说明：ccproxy 默认开启 `client_key_passthrough`——这里的
> `ANTHROPIC_API_KEY` 填**真实中转站密钥**（ccproxy 直接拿去调上游）；填
> `dummy` 也行，但需要已设置后备密钥（dashboard 或 `.env`），401 后会自动
> 落到后备密钥上。

---

## 四、与 cc-switch 配合使用

[cc-switch](https://github.com/farion1231/cc-switch) 是一个开源桌面工具，用于在
多个 API 供应商之间一键切换 Claude Code（以及 Codex 等）的配置：它把
endpoint、密钥、模型写进 Claude Code 自己的 `~/.claude/settings.json`，配合
Claude Code v2.0.69+ 的热切换，切换时无需重启终端。

ccproxy 对 Claude Code 来说只是一个普通的 Anthropic 兼容端点，所以在
cc-switch 里把它加成一个**自定义供应商**即可：

| cc-switch 字段      | 填什么                   | 说明                                       |
| ------------------- | ------------------------ | ------------------------------------------ |
| endpoint / Base URL | `http://127.0.0.1:18181` | 与 `CCPROXY_PORT` 保持一致                 |
| API key             | **真实的中转站密钥**     | ccproxy 直接用它调上游（见下文"密钥来源"）  |
| 模型名              | 如 `claude-opus-4-8`     | ccproxy 原样透传给中转站                   |

切换到该供应商 = 走 ccproxy（修流、修 JSON、代理网络搜索全部生效）；切到
其他供应商 = 直连其他中转站。ccproxy 容器对此无感知，切回来即恢复使用。

**密钥来源（client_key_passthrough）**：ccproxy 默认开启
`client_key_passthrough`——上游调用**优先使用客户端请求带来的密钥**，也就是
cc-switch 配置的真实密钥，由 cc-switch 统一管理所有供应商的密钥。后备
规则：若上游返回 401/403（比如客户端密钥过期），ccproxy 会自动改用后备密钥
（dashboard 或 `.env` 里设置的）重试一次。请求日志中会标注本次用的来源
（`key=client` / `key=config`）。

**纯 cc-switch 模式**：完全可以不设任何后备密钥——ccproxy 允许无密钥启动，
此时上游调用完全依赖客户端带来的密钥；dashboard 顶部的 key 状态会显示
`client-supplied`，API key 面板显示"未设置后备密钥"。要恢复后备，随时在该
面板保存一个即可。注意：面板保存的密钥写在容器内，`docker restart` 会保留，
但**重建容器**（`docker compose up -d --build` / `down` + `up`）会丢失——
若要重建后也不丢，挂载一个 `.env` 文件（见[六](#六可选的-env)）。

**前提：`ENABLE_TOOL_SEARCH=false` 必须设置。** 这是 ccproxy 的硬性要求；
`run-claude` 脚本会设它，但走 cc-switch 时没有这层包装，请把它写进
Claude Code 全局配置的 `env` 块——一次性设置，cc-switch 切换供应商时会
保留用户自己的环境变量：

文件：`~/.claude/settings.json`（Windows：`%USERPROFILE%\.claude\settings.json`）

```json
{
  "env": {
    "ENABLE_TOOL_SEARCH": "false"
  }
}
```

注意事项：

* **避免双重代理**：cc-switch 自带"路由模式"（本地转发/聚合，默认
  `127.0.0.1:15721`）。与 ccproxy 结合时请用它的**直连（Direct）模式**直接
  指向 ccproxy；不要把请求链叠成 Claude Code → cc-switch 路由 → ccproxy →
  中转站——链路虽可能通，但出问题难以排查，且没有额外收益。
* **与启动脚本的关系**：cc-switch 修改全局 `settings.json`，而
  `run-claude.sh` / `run-claude.bat` 用临时 `--settings` 文件启动、不碰全局。
  两者可以共存，但同一次会话请选定一种方式，避免全局指向与临时指向互相
  覆盖造成困惑。
* **远程部署**：ccproxy 的 Docker 跑在服务器、Claude Code 在本机时，
  endpoint 填 `http://服务器IP:端口`，并按[安全须知](#九安全须知)放开
  `CCPROXY_BIND` 与防火墙。

---

## 五、日常操作

### 改 API 密钥（网页操作，立即生效）

打开 <http://127.0.0.1:18181/>，页面底部有 **API key** 面板：

1. 显示当前后备密钥（掩码，如 `sk-abc...wxyz`）；未设置时显示客户端密钥
   模式标签
2. 在输入框粘贴新密钥，点 **Save key**
3. **立即生效，无需重启**。持久化范围：`docker restart` 保留；重建容器
   （`up -d --build` / `down` + `up`）会丢，除非挂载了 `.env`

也可用命令行：

```sh
curl http://127.0.0.1:18181/api/key
# {"key_set": true, "masked": "sk-abc...wxyz", "passthrough": true}

curl -X POST http://127.0.0.1:18181/api/key \
  -H "Content-Type: application/json" -d '{"api_key": "sk-新密钥"}'
# {"ok": true, "key_set": true, "persisted": true}
```

### 改端口

默认宿主端口是 **18181**，容器内部端口（8181）不用动：

1. 改端口只需设置环境变量 `CCPROXY_PORT`（例：改成 28181），也可以放进
   可选的 `.env` 文件：

   ```sh
   CCPROXY_PORT=28181 docker compose up -d
   curl http://127.0.0.1:28181/health
   ```

2. 之后 Claude Code 侧相应更新：cc-switch 的 endpoint，或
   `PROXY=http://127.0.0.1:28181 sh run-claude.sh`

不用 compose、直接 `docker run` 的话，改 `-p` 左侧即可：
`-p 127.0.0.1:28181:8181`。

### 看日志

```sh
docker logs -f ccproxy
```

与本地安装的 `ccproxy_log.txt` 内容一致。要取日志文件本身：

```sh
docker cp ccproxy:/app/ccproxy_log.txt .
```

### 停止 / 重启 / 升级

| 操作           | 命令                                                                 |
| -------------- | -------------------------------------------------------------------- |
| 停止并移除容器 | `docker compose down`                                                |
| 重启           | `docker restart ccproxy`                                             |
| 升级到新代码   | `git pull` 然后 `docker compose up -d --build`（依赖层有缓存，很快） |

默认 `restart: unless-stopped`：宿主机重启或 Docker 服务重启后容器会自动恢复运行。

> 升级属于"重建容器"：dashboard 里保存的后备密钥会随之丢失（cc-switch 模式
> 不受影响），重新保存一次或挂载 `.env` 即可。

---

## 六、可选的 .env

`.env` **不再是必需文件**。需要以下任一能力时才创建它（已被 git 忽略，
不会被打进镜像）：

| 变量               | 谁在用            | 作用                   | 默认值        |
| ------------------ | ----------------- | ---------------------- | ------------- |
| `UPSTREAM_API_KEY` | ccproxy           | 后备中转站密钥         | 无            |
| `TARGET_URL`       | ccproxy + compose | 覆盖中转站地址         | 用 config.json |
| `CCPROXY_PORT`     | compose           | 宿主机发布端口         | `18181`       |
| `CCPROXY_BIND`     | compose           | 宿主机绑定网卡         | `127.0.0.1`   |

两个用法：

1. **只给 compose 用**（改端口/网卡/中转站地址）：在项目目录创建 `.env`
   写入相应变量即可，compose 会自动读取做替换；`UPSTREAM_API_KEY` 在这个
   用法下**不会**进入容器（密钥走客户端或 dashboard）。

   ```ini
   CCPROXY_PORT=28181
   TARGET_URL=https://另一个中转站
   ```

2. **还要后备密钥且重建容器不丢**：在 `.env` 写入密钥，并在
   `docker-compose.yml` 里恢复挂载（文件必须先存在）：

   ```ini
   UPSTREAM_API_KEY=sk-你的密钥
   ```

   ```yaml
       volumes:
         - ./.env:/app/.env
   ```

优先级：真实环境变量 > `.env` > `config.json`。

---

## 七、挂载自定义 config.json

镜像内置了仓库默认的 `config.json`（`api_key` 为空）。想改历史预算、模型、
功能开关等又不想重新构建时，把自己的配置只读挂载进去（在
`docker-compose.yml` 的 `volumes:` 下添加）：

```yaml
      - ./config.json:/app/config.json:ro
```

环境变量与 `.env` 的优先级始终高于该文件。

---

## 八、常见问题

**容器反复退出，`docker logs ccproxy` 显示 `UPSTREAM_API_KEY is not set`**
默认不会发生（无密钥也能启动，进入客户端密钥模式）。该错误只在配置里
关闭了 `client_key_passthrough` 且没有任何密钥时出现——设置密钥（cc-switch
/ dashboard / `.env`），或重新开启该开关，然后 `docker compose up -d`。

**`18181 端口被占用`**
按上文"改端口"一节换一个端口。

**改了密钥但请求仍报 401**
若走的是客户端密钥（cc-switch），新密钥已即时生效，401 说明密钥本身不对
（或该中转站已作废它），去中转站控制台核对；同时确认有后备密钥时它也有效。

**`docker compose up` 报错提到 bind mount / `.env` 路径**
只有在你自己恢复了 `.env` 挂载、而文件又不存在时才会发生——先创建 `.env`
再 `up`。

**Windows 上没有 curl**
直接用浏览器打开 <http://127.0.0.1:18181/health>，看到 JSON 即正常。

**想彻底重来**

```sh
docker compose down
docker compose up -d --build
```

---

## 九、安全须知

* 代理本身**没有鉴权**：谁能访问到端口，谁就能消耗你的（后备）密钥。因此
  compose 默认只绑定宿主机 `127.0.0.1`。
* 确实要让局域网/其他机器访问时，设置 `CCPROXY_BIND=0.0.0.0`，
  **并**配合防火墙限制来源，或在前端加一层带鉴权的反向代理。
* 可选的 `.env`（若你创建了）已被 `.gitignore` 忽略、被 `.dockerignore`
  排除——请勿提交到仓库，也不会被打进镜像。
* 密钥只发往你在 `config.json` / `TARGET_URL` 里配置的中转站。

---

## 十、镜像细节

* 基础镜像 `python:3.12-slim`（ccproxy 支持 3.9+）
* 以专用非 root 用户 `ccproxy` 运行；`/app` 目录归属该用户（ccproxy
  会在自身目录写日志与调试转储）
* 只复制 `ccproxy.py`、`dashboard.py`、`config.json`、`requirements.txt`
  与许可/README 进镜像——测试、探针、宿主机脚本均不进入
* ccproxy 自行处理 `SIGTERM`，`docker stop` 可干净退出
* 内置 `HEALTHCHECK` 每 30 秒探测一次 `/health`（容器内部仍是 8181）
