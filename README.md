# astrbot_plugin_jm_download

AstrBot JM 下载插件。发送 `/jm [num]` 后，插件会调用 `jmcomic` 下载指定 album，合成为 PDF，用编号作为密码打包为 zip，并通过平台文件消息发送。

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
- `image_threads`：图片下载线程数，默认 `2`，适合 1GB 内存左右的小服务器。
- `cleanup_images`：生成 PDF 后清理图片目录，默认开启。
- `keep_zip`：发送后保留 zip，默认开启。

每个编号使用独立工作目录：`<base_dir>/<num>/`。最终产物为 `<num>.pdf` 和 `<num>.zip`。

## 平台限制

不同平台适配器对文件消息支持不一致。若文件发送失败，插件会回复服务器本地 zip 路径，管理员可从该路径取文件。

## 合规提醒

请仅下载、传播你有权访问和保存的内容，并遵守所在地区法律法规、平台规则和目标站点条款。本插件只封装 `jmcomic` 下载能力，不提供内容审核、版权判断或访问授权。
