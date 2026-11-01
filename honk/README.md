# honk 配置与规则

这里统一维护 honk 的 `.dae` 配置、规则源、构建脚本和 `.dat` 数据库。

## 配置

`config.dae` 保留原 dae 的 DNS 分流、IPv4 优先与 IPv6 回退、853/UDP443 阻断、国内 IP 强制直连与 Doona 设置，网卡为 br-lan。策略组已按 Mihomo YAML 类似层级重构：服务选择器 → 地区策略 → 节点。Final 改为可手动选择的漏网流量组，默认选择 Proxy，不再固定为 score。

**公开配置的订阅 URL 是占位符。使用前在本机替换，勿把真实订阅提交到仓库。**


## 策略组结构

Proxy 是总选择器，不再等同香港。AI、YouTube、Google、Github、Telegram、TikTok、Netflix、Wallet、Steam、Microsoft、OneDrive、Apple、Final 都是独立服务选择器，可以选择同一套地区策略，也可以选 Proxy 或 direct。

| 地区 | 手动选择节点 | 自动测速 | 负载均衡 | 故障转移 |
|---|---|---|---|---|
| 香港 | HK | HK-Auto | HK-LoadBalance | HK-Fallback |
| 日本 | JP | JP-Auto | JP-LoadBalance | JP-Fallback |
| 美国 | US | US-Auto | US-LoadBalance | US-Fallback |
| 新加坡 | SG | SG-Auto | SG-LoadBalance | SG-Fallback |

另外提供 All（全部节点手动）、Auto（全部节点自动）、LoadBalance（全部节点轮询）、Other（其他地区手动）及显式 direct。组名采用 ASCII，原生策略分别为 select、min_moving_avg、loadbalance、fallback；负载均衡是对新连接分配节点，不是让单个下载叠加多条线路。

默认选择：Proxy/Google/Github/Telegram/Steam/Apple → HK-Auto；AI/TikTok/Wallet/Microsoft/OneDrive → JP-Auto；YouTube → US-Auto；Netflix → SG-Auto；Final → Proxy。地区没有匹配到节点或全部不可用时失败关闭，不会暗中跨地区或直连；可在服务组主动选择其他地区、Auto、All 或 direct。

Apple Push 专用规则改为 HK，以免随总 Proxy 切换地区。其他 routing 表达式和优先级保持不变。自动测速 tolerance 为 20ms；沿用全局 30s 探测间隔，不写无效的每组 interval。选择变化会中断受影响的连接。

共 34 组，最大嵌套深度 3。`groups.json` 为生成的映射；结构源在 `scripts/update_groups.py`。修改结构后运行：

```sh
python honk/scripts/update_groups.py
python honk/scripts/validate_groups.py
```

本次静态验证已覆盖组引用、默认成员、循环、层级、筛选正则和路由目标；尚未在用户路由器的 honk 原生加载器运行。不需要修改数据库就能调整组选择。修改 `.dae` 需要在路由器上应用配置；Geo 自动更新只更新数据库，不会自动替换 `.dae` 或订阅。

## 日常维护

- 自建文本规则：编辑 `honk/rules/*.list`。
- 外部规则来源与分类名：`honk/sources.json`。
- 生成脚本：`honk/scripts/`。
- 运行数据库与校验值：自动生成到 `honk/dat/`。

`honk/rules/` 是 honk 自建规则的唯一维护位置。它们最初从现有列表导入，以后修改根目录 `rules/` 不会自动同步到这里，避免影响其他代理配置。

推送规则或构建脚本修改后，GitHub Actions 自动生成数据库；也可手动运行 **Build honk databases**。定时任务为北京时间每日 04:20（GitHub 可能延迟），刷新外部规则和官方基础数据。仅所有下载、解析及二进制往返校验通过后才提交结果。失败保留上一次成功数据库，不会部分提交。

## 数据库

- `custom-geosite.dat` / `custom-geoip.dat`：只有自建补充分类。
- `geosite.dat` / `geoip.dat`：官方分类 + 自建分类的合并版本，**供 honk 实际使用**。

honk 当前只按固定名称加载 geosite.dat / geoip.dat，不支持在 routing 中另指定第三份 custom.dat。所以维护层面分开，运行时合并。

固定下载地址（首次工作流成功后生效）：

```text
https://raw.githubusercontent.com/blank-cat-1/rule/main/honk/dat/geosite.dat
https://raw.githubusercontent.com/blank-cat-1/rule/main/honk/dat/geoip.dat
```

配置模板已引用这两个地址。honk 的远程下载源与自动更新计划是两件事：`assets.geodata` 设置下载源；自动更新计划需要在 Doona/Native API 中另行设置，不能用 subscription.interval 代替。数据库下载和应用的实际成功状态以 honk/Doona 的日志为准。

## 分流优先级

原 dae 开头的 private/cn IP direct(must)、853 和 UDP443 阻断继续优先。自建例外放在这些基础规则之后、原服务域名规则之前。已有 Apple、AI、Wallet、Steam 等策略不被 YAML 同类设置替换。

需要自建的原生分类使用 `mig-` 前缀，标准库已有分类直接复用。MRS 均由固定版本的官方 Mihomo 工具解码；下载工具时核对 GitHub release asset SHA256。Mihomo 只参与构建，不需要安装在路由器上。

## 本地构建

Linux x86_64 使用 Python 3.10+：

```sh
python honk/scripts/build.py
```

也可指定对应平台已安装的官方 Mihomo：

```sh
python honk/scripts/build.py --mihomo /path/to/mihomo
```

脚本不读取订阅、不登录路由器、不安装、不重启服务。已做静态/数据校验；未在用户路由器上验证 honk Rust 加载器、内核挂载或节点连通。

官方依据：[routing/Geo 规则](https://github.com/daeuniverse/honk/blob/main/doc/en/reference/routing.md)、[assets 下载设置](https://github.com/daeuniverse/honk/blob/main/doc/en/reference/assets.md)。

## DNS：IPv4 优先，保留 IPv6 回退

`dns.ipversion_prefer: 4` 使用原生 preferipv4 策略；移除了此前的 `qtype(aaaa) -> reject`，保留其余 DNS 请求/响应分流及两个上游。v0.1.0-beta.1 的官方解析器和文档已经支持此设置。

注意：IPv6 回退是 DNS 地址族策略：IPv4 无地址或优先族解析遇到普通可用性失败时，允许返回 IPv6；不是保证任意 IPv4 TCP 连接失败后再改走 IPv6。客户端自带 DoH 绕过 honk 时也不受此 DNS 设置控制。

修改仓库不会自动替换路由器的 `.dae`。将配置应用到实际文件后重新加载 honk 即可，无须重新构建固件、数据库或重启路由器。当前检查仅做官方版本支持和静态结构验证，未远程连接路由器或运行原生加载器。

## 原始路由为基础与数据库去重

原始 config.dae 的全部 routing 表达式、目标和相互顺序继续保留，仅补入缺少的匹配。现有 34 个策略组、IPv4 优先与 IPv6 回退、DNS 分流、订阅和 Doona 设置不变。

自建数据库只保留 8 个补充 provider：muse、proxy-rule、jp-proxyrule、Apple_Push、anti-ad、direct、proxylite、apple_ip。以下分类不再重复抓取或生成，配置改用标准数据：

| 删除的重复分类 | 使用的标准分类 |
|---|---|
| mig-cn-domain | geosite: cn |
| mig-cn-ip | geoip: cn |
| mig-google-ip | geoip: google |
| mig-netflix-ip | geoip: netflix |
| mig-private-domain | geosite: private |

去重时核对：国内域名 110,177 条记录相同；国内 10,012、Google 8,559、Netflix 122 条 CIDR 的地址覆盖完全相同。标准 private 包含迁移版的全部 132 条，另有一条匹配单标签主机名的正则；以标准库为准，因此这些本地主机名也会直连。

末尾 geoip:cn 的普通 direct 保留：开头 direct(must) 排除了 53/853，条件不同，不把它当成无条件重复删除。两条规则引用同一份标准 cn 数据，不存在复制数据库分类。

构建在发布前检查全部 routing/DNS Geo 分类和属性确实存在、且有有效条目，并禁止已删除的重复分类重新进入运行库和自建库。官方库缺分类时构建失败，保留上一次发布，不会发布匹配为空的文件。

## 独立精简版：仅一个自动组、一个手动组

完整版 `honk/config.dae` 原样保留。另提供 `honk/config-lite.dae`，全局只有两个组：

- **Auto**：对所有地区的有效节点自动测速选择，policy 为 min_moving_avg、tolerance 为 20ms。
- **Manual**：手动选择 Auto、单个有效节点或显式 direct；默认 Auto。

所有代理规则统一指向 Manual，匹配条件、顺序、DIRECT/REJECT 以及 IPv4 优先/IPv6 回退、DNS 分流、订阅和 Doona 设置保留。精简版不再分别选择 HK/JP/US/SG，也不再对 Muse、日本规则、Apple Push 锁定地区：这些服务均跟随 Manual，区域限制需通过手动选节点满足。没有健康节点时 block，不隐式转为直连。

两个版本共用 `honk/dat/`，不需要新建或复制数据库。只选一份配置作为运行入口，不要把两份配置同时 include。公开文件中的订阅仍为占位符，实际订阅只在路由器本地填写。

完整版后续变更后，可重新生成并验证精简版：

```sh
python honk/scripts/make_lite.py
python honk/scripts/validate_lite.py
```

生成器拒绝使用相同的输入/输出路径，不会覆盖完整版。CI 同时校验两版结构；若完整版规则/DNS 变化，需同步重新生成精简版再提交。路由器只有 Geo 自动更新，不会自动切换或覆盖 `.dae`；使用精简版需主动应用该配置并重新加载 honk，无需重启整台路由器。
