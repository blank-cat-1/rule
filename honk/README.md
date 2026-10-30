# honk 配置与规则

这里统一维护 honk 的 `.dae` 配置、规则源、构建脚本和 `.dat` 数据库。

## 配置

`config.dae` 以原 dae 配置为底稿，仅补入缺少的规则和 US/JP 组。原 14 个服务组、DNS、AAAA 拒绝、853/UDP443 阻断、国内 IP 强制直连、Final score 和 Doona 设置保留；网卡为 br-lan。

**公开配置的订阅 URL 是占位符。使用前在本机替换，勿把真实订阅提交到仓库。**

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

追加的原生分类使用 `mig-` 前缀。MRS 均由固定版本的官方 Mihomo 工具解码；下载工具时核对 GitHub release asset SHA256。Mihomo 只参与构建，不需要安装在路由器上。

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
