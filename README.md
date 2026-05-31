# astrbot_plugin_jm_download

AstrBot JM 下载插件。发送 `/jm [num]` 后，插件会调用 `jmcomic` 下载指定 album，合成为 PDF，用编号作为密码打包为 zip。默认在 QQ/OneBot 中直接上传 zip 文件；如果不是 QQ 事件或上传失败，会降级为 AstrBot 文件服务下载链接或本地路径。

## 用法

```text
/jm 1424612
```

只接受一个纯数字参数。缺失参数、非数字或多个参数都会返回：

```text
格式错误，正确格式：/jm [num]，例如：/jm 1424612
```

下载成功后会回复编号、页数和 zip 密码；zip 密码就是 album 编号。

## 依赖

插件依赖 `requirements.txt`：

- `jmcomic>=2.6.20`
- `img2pdf`
- `pyzipper`

AstrBot 通常会在加载插件时自动安装依赖；如果自动安装失败，请在 AstrBot 运行环境中手动安装。

## 配置

配置项在 `_conf_schema.json` 中定义，可在 AstrBot WebUI 修改：

- `base_dir`：下载产物目录。留空时使用 AstrBot `data/jm_downloads`。
- `client_impl`：`html` 或 `api`，默认 `html`。
- `domain`：JM 域名，默认 `18comic.vip`。
- `proxy`：代理地址。`system`、`none` 或空值表示不显式配置代理。
- `avs_cookie`：可选 AVS Cookie。
- `image_threads`：图片下载线程数，默认 `1`，适合 1GB 内存左右的小服务器。
- `cleanup_images`：生成 PDF 后清理图片目录，默认开启。
- `delivery_mode`：zip 投递方式，默认 `qq_file`。`qq_file` 会调用 QQ/OneBot 的 `upload_group_file` 或 `upload_private_file` 上传 zip；`link` 会发送 AstrBot 文件服务下载链接，如果没有配置 `callback_api_base` 且当前是 QQ 事件，会自动降级为 QQ 文件上传；`path` 只回复服务器本地路径；`file` 使用平台文件消息。
- `file_link_ttl`：`delivery_mode=link` 时下载链接有效期，默认 `3600` 秒。
- `keep_zip`：发送后保留 zip，默认开启。

每个编号使用独立工作目录：`<base_dir>/<num>/`。最终产物为 `<num>.pdf` 和 `<num>.zip`。

## 平台限制

不同平台适配器对文件消息支持不一致，并且部分平台上传文件时会把整个 zip 读入内存。QQ/OneBot 建议保持默认 `delivery_mode=qq_file`，这会绕过 AstrBot 文件消息组件，并按顺序尝试普通本地路径、`file://` 路径、AstrBot 文件服务 URL。如果协议端和 AstrBot 不在同一文件系统内，建议在 AstrBot 主配置中设置可访问的 `callback_api_base`，让 URL 候选也可用。

## 合规提醒

请仅下载、传播你有权访问和保存的内容，并遵守所在地区法律法规、平台规则和目标站点条款。本插件只封装 `jmcomic` 下载能力，不提供内容审核、版权判断或访问授权。
