<div align="center">

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/logo.svg" width="72" alt="TextFold">

# TextFold

**折叠任何文字，从一屏地图到每一个字**

<sub>原名 PaperFold</sub>

<img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-6B5CE7?style=flat-square">
<img alt="在你的电脑上运行" src="https://img.shields.io/badge/runs-on_your_computer-E08A3C?style=flat-square">
<a href="https://github.com/chenxiachan/textfold/blob/main/LICENSE"><img alt="Apache 2.0 许可证" src="https://img.shields.io/badge/license-Apache_2.0-6B5CE7?style=flat-square"></a>

[English](https://github.com/chenxiachan/textfold/blob/main/README.md) · **简体中文**

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/sources-dark.webp">
  <img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/sources.webp" width="880" alt="TextFold 能读的：arXiv、PubMed Central、bioRxiv、medRxiv、维基百科、GitHub README、任意网页、PDF、Word、PowerPoint、Excel、EPUB、HTML、图片、Markdown、纯文本、CSV，以及 agent 的回答，从全文一路折到几个词">
</picture>

**粘贴链接：** 任意网页 · arXiv · PubMed Central · bioRxiv · medRxiv · 维基百科 · GitHub<br>
**拖入文件：** PDF · Word · PowerPoint · Excel · EPUB · HTML · CSV · 图片 · Markdown · 纯文本

**[试用演示 →](https://chenxiachan.github.io/textfold/gallery/)** 或者 **[下载软件 ↓](#开始使用)** · [最新 ↓](#最新)

<br>

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/zoom-zh.gif" width="880" alt="一篇论文从全文折叠成章节地图，再展开回来">

</div>

## 读长文，脑子里少装一点

自由选择你需要的文字信息层级，降低认知负担。

| | 层级 | 每一段变成 | 谁的话 |
|:-:|---|---|---|
| **1** | **全文** | 原样的段落 | 作者 |
| **2** | **简述** | 一到三句关键原句，一字不改 | 作者 |
| **3** | **关键句** | 这一段的要点和理由 | AI，依据是简述里那几句 |
| **4** | **要点** | 一行，挂在本节的主线上 | AI |
| **5** | **主题** | 几个词；整篇变成一张章节卡片地图 | AI |

## 也可以用在 Agent 输出上

Agent 写的，总比你有空读的多。一个 [Claude Code mod](https://code.claude.com/docs/en/plugins/mods/overview) 用同样的方式折叠每条回答，一个键一个层级；Pi 里也有一个扩展做同样的事。[了解更多 ↓](#在-claude-code-和-pi-里)

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/textfold.gif" width="880" alt="Claude Code 里的一条回答从全文折到每段两句，再折到一句，然后展开回来，每次按一个键">

## 一种折叠，三个地方

- **读。** 粘贴链接或拖入文件，打开就是一张章节地图，再往里缩放。[开始使用 ↓](#开始使用)
- **折叠 agent 的回答。** 在 Claude Code 和 Pi 里一个键一个层级，不用第二个模型。[在 Claude Code 和 Pi 里 ↓](#在-claude-code-和-pi-里)
- **接入你的工作流。** `python3 -m textfold get` 把文档一层一层地交给你的 agent 或脚本；开放的格式让任何程序都能读写折叠后的文字。[给 agent 用 ↓](#给-agent-和脚本用)

## 你会得到

- **词会移动，不会被换掉。** 缩放时，留下的词滑到新的位置，其余的在周围淡出。
- **缩放跟着手指走。** 可以停在半路、往回退，也可以只展开一段。

- **对照原文。** 论文或 PDF 的原页可以放在旁边，读到哪一段，就标出它在原页上的位置。
- **针对内容，结构化地问 AI。** 选中一段，或者就全文提问。回答先给结论，再列依据，每条依据都标出原文段落，点一下就到。
- **笔记跟着缩放。** 在页边高光、写笔记，缩小时标过的内容依然在，也会和整页一起保存。

- **用你的语言读。** 支持多种语言，逐句翻译，公式保持原样。

- **你的文献库，井井有条。** 用 ⌘K 搜索；建文件夹整理文档，拖进去或者右键移进去；按类型、添加时间或最近打开排序。

<table>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/notes.png" alt="全文里的高光和页边笔记"></td>
<td width="50%"><img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/keep.png" alt="高光过的句子在要点层被保留"></td>
</tr>
<tr>
<td align="center"><sub>在全文里高光、在页边写笔记……</sub></td>
<td align="center"><sub>……缩小时，标过的内容依然在。</sub></td>
</tr>
</table>

## 直接读你的 Zotero

点拖放框下面的 **Zotero 文献库**，你的文献库就按 Zotero 里的样子出现：分类、群组文献库、搜索都在。任何条目点 **阅读** 就能打开。

- **arXiv 上有的条目**，从 arXiv 读。其他条目读它的 PDF，PDF 放在旁边对照；没有 PDF 就读它附带的 EPUB、保存的网页或 Word 文件。只有 DOI 的条目，从 Europe PMC 读。
- **你在 Zotero 里填的信息都保留**：标题、作者和 citekey。
- **一切都在你的电脑上。** TextFold 读的是你已经在用的 Zotero 应用，和引文插件的方式一样：不需要账号和密钥，不向 Zotero 的服务器发送任何东西，也不会改动你的文献库。

打开方法：在 Zotero 7 里勾选 **设置 › 高级 › 允许此计算机上的其他应用程序与 Zotero 通信**。

## 开始使用

**[下载软件](https://chenxiachan.github.io/textfold/zh.html#download)**，有 macOS（Apple 芯片或 Intel）和 Windows 版。需要的东西都在里面，包括 Python。

也可以装 Python 包，任何系统都能用，也能接进你自己的流程：

```bash
python3 -m pip install textfold
python3 -m textfold serve
```

在浏览器里打开 `http://localhost:3017`。第一次使用先[连接一个模型](#连接模型)，然后粘贴链接或拖入文件，再选择语言。需要 Python 3.9 或更新的版本（macOS 自带的就可以）。

| 粘贴或拖入 | TextFold 读到的 |
|---|---|
| 论文的链接或 DOI：arXiv、PubMed Central、bioRxiv、medRxiv | 网站上结构化的正文（arXiv 论文没有 HTML 版本时读它的 PDF；其他 DOI 要在 Europe PMC 有开放全文） |
| 其他任何网页 | 它的正文，去掉菜单、广告，以及网页对读者隐藏的文字 |
| 维基百科条目、GitHub 仓库 | 条目；README，连同里面的图 |
| PDF | 如果它是网上能读到的论文，就读网上的版本，你的文件放在旁边对照；其他 PDF 在你的电脑上读：不装引擎 TextFold 自己就能读，图也会裁出来；装了 PDF 引擎读得更完整（MinerU，约 3.4 GB，在首页安装一次即可），扫描件需要它 |
| Word、PowerPoint、Excel 文件，CSV、EPUB、保存的网页 | 文档本身，标题、表格、图片和公式都保留：不装引擎 TextFold 自己就能读，装了 PDF 引擎读得更完整 |
| 图片 | 由 PDF 引擎识别出的文字 |
| Zotero 文献库里的条目 | 有 arXiv 版本就读 arXiv，否则读它的 PDF 或其他附件，再没有就按 DOI 读。[直接读你的 Zotero ↑](#直接读你的-zotero) |
| Markdown 或纯文本文件 | 原样的文件 |

读过的文档保存在系统存放应用数据的文件夹里，和桌面 App 共用。

<details>
<summary>也可以直接从代码运行</summary>

```bash
git clone https://github.com/chenxiachan/textfold.git
cd textfold
python3 -m pip install -r requirements.txt
python3 -m textfold serve
```

这样文档保存在代码目录里。

</details>

## 连接模型

TextFold 用你已有的模型，不需要注册账号。启动时它会自己去找；一个都没找到时，首页会给出接入的方式。

| 你有 | 怎么做 |
|---|---|
| Claude Code、Codex、Pi 或 WorkBuddy | 什么都不用做，TextFold 会自动找到并使用（WorkBuddy 用你登录的账号和它的模型）。 |
| ChatGPT 订阅 | 点 **使用我的 ChatGPT 订阅**。电脑上会启动一个小的本地桥，用你的账号登录（需要 Node.js）。 |
| 什么都还没有 | 点 **OpenRouter 一键授权**。授权一次，免费模型马上可用。 |
| 一个 API key | **设置 › 添加供应商**：Anthropic、OpenAI、DeepSeek、通义千问、智谱 GLM、Kimi、MiniMax、Google、Ollama，或任何 OpenAI 兼容接口。 |

回答问题可以用比生成层级更强的模型：**设置 › 模型 › 回答问题**，还可以选推理强度。

## 阅读时的操作

| 操作 | 作用 |
|---|---|
| 双指捏合，或 ⌘ / Ctrl 加滚轮 | 围绕鼠标所在处缩放 |
| `1` 到 `5` | 跳到某一层 |
| 点击某一段 | 只展开这一段 |
| 点击图片 | 放大查看 |
| 顶部的 **原文** | 对照原文 PDF 阅读 |
| 顶部的 **保存** | 把整页存成一个文件，或者只存你的标注 |
| 选中文字 | 高光、写笔记或追问 |
| 右下角 **问全文** | 就整篇提问 |
| `L` | 切换到下一种语言 |
| `⌘K`（Ctrl+K）或 `/` | 搜索文献库 |

## 给 agent 和脚本用

`python3 -m textfold get` 一次给出一份文档的一个层级，从最概括的开始。agent 可以先读地图，再决定把上下文花在哪一节：

```bash
python3 -m textfold get https://arxiv.org/abs/2512.23916        # 地图：每一节的主题
python3 -m textfold get 2512.23916 --level key --section 3      # 某一节：每个要点和它的理由
python3 -m textfold get report.pdf --json                       # 整份文档，TextFold 格式
```

还没折叠过的文档会先用你连接的模型折叠。模型写的每一行都标明是模型写的，并且指回它依据的作者原句：[docs/format.md](https://github.com/chenxiachan/textfold/blob/main/docs/format.md) 说明了这个格式，任何读写折叠文本的程序都可以用。

## 保存一页

阅读页顶部的 **保存** 把一页存成一个 HTML 文件，不需要服务器，在哪里都能打开：各个层级、你选的标注，还可以带上原文 PDF 在左边对照。也可以只存你的标注，存成网页、PDF、Obsidian 用的 Markdown 或 JSON。命令行也能导出这一页，只是不带你的标注：

```bash
python3 -m textfold export 2512.23916
```

TextFold 只是一个工具，它的许可证只管代码。分享文件时，请遵守原文的许可条款，它标在每篇的标题下方。

## 在 Claude Code 和 Pi 里

TextFold 把五个层级放到 Claude Code 和 Pi 的每条回答上。按 5 看一句话的答案，按 3 看每段的要点，按 1 看每一个字（在 Pi 里要按住 Alt）。不做任何改写，所以无论在哪一级，你读到的都是模型的原话。

<details>
<summary><b>在 Claude Code 里：安装，以及每一级能看到什么</b></summary>

<br>

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/textfold.gif" width="880" alt="Claude Code 里的一条回答从全文折到每段两句，再折到一句，然后展开回来，每次按一个键">

需要 Claude Code 2.1.287 或更新的版本，在终端里或桌面应用的 Code 标签页里都能用。

```bash
claude plugin marketplace add chenxiachan/textfold
claude plugin install textfold@textfold
```

| 键 | 层级 | 你看到的 |
|:-:|---|---|
| **1** | **Full** | Claude 写的每一个字 |
| **2** | **Brief** | 每个要点，连同背后的理由 |
| **3** | **Points** | 只看要点，一眼扫完 |
| **4** | **Outline** | 长回答的地图：有哪几节，每节讲了什么 |
| **5** | **Gist** | 一句话的答案 |

在提示框为空时输入数字，或者在提示框上方那一行里选一个层级。短回答保持原样：不到大约 80 个词（中文约 130 字），或者折叠后几乎不会变短的回答，总是原样显示。

**默认层级。** 每个会话默认从 Full 开始。想换成别的层级，运行 `/config`，设置 **Starting level**；会话里照样可以用提示框上方那一行或数字键 1 到 5 切换。

**为什么折叠可信。** TextFold 请 Claude 把要点放在前面：每条回答先给答案，每段先写关键句。折叠保留的就是 Claude 放在最前面的内容。没有第二个模型，也不做摘要，所以折叠不花钱、不用等。

详见 [plugins/textfold](https://github.com/chenxiachan/textfold/blob/main/plugins/textfold/README.md)。

</details>

<details>
<summary><b>在 Pi 里：安装，看它怎么折叠</b></summary>

<br>

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/pi.gif" width="880" alt="Pi 里的一条回答逐级折叠，从全文一直折到一句话的答案，每级一个键">

一个扩展把同样的五个层级放到 [Pi](https://pi.dev) 的每条回答上。需要 Pi 1.2.0 或更新的版本，Node 22.15 或更新。

```bash
git clone https://github.com/chenxiachan/textfold.git
pi install ./textfold/plugins/pi-textfold
```

按住 Alt 再按数字，或者输入 `/fold` 加层级：`/fold 3`、`/fold points`、`/fold off`。每条回答都在原处折叠，之前的回答也一样；提示框上方那一行标出你正在读的层级。它用的就是 mod 的折叠引擎，所以同一条回答在 Claude Code 和 Pi 里每一级读到的都一样。

详见 [plugins/pi-textfold](https://github.com/chenxiachan/textfold/blob/main/plugins/pi-textfold/README.md)。由 [@jlamweil](https://github.com/jlamweil) 贡献。

</details>

## 最新

- **2026 年 10 月 19 日：更多阅读语言。** 新增瑞典语、丹麦语、挪威语、芬兰语、荷兰语、波兰语、捷克语、乌克兰语、土耳其语、印尼语和越南语。界面没有这种语言时显示英文。感谢 [@Kullenej](https://github.com/Kullenej)。
- **2026 年 10 月 15 日：Pi 的回答也能折叠了。** [Pi 扩展](https://github.com/chenxiachan/textfold/blob/main/plugins/pi-textfold/README.md) 把五个层级放到每条回答上，折法和 Claude Code 里一样。感谢 [@jlamweil](https://github.com/jlamweil)。
- **2026 年 10 月 15 日：不装 PDF 引擎也能读 PDF。** 自带文字的 PDF（大多数论文都是）直接打开，图从原页上裁出来；只有扫描件还需要 PDF 引擎。没有 HTML 版本的 arXiv 论文改读它的 PDF。感谢 [@sylvainHellin](https://github.com/sylvainHellin)。
- **2026 年 10 月 15 日：你的文献库和你的提问。** 文献库可以搜索、建文件夹，按添加时间或最近打开排序。提问有了发送和停止键，对话里任何一轮都可以删掉，回答问题还可以用比生成层级更强的模型。感谢 [@suhyungJang](https://github.com/suhyungJang)。
- **2026 年 10 月 14 日：Mac 和 Windows 软件。** 下载 TextFold 的 macOS 版（Apple 芯片或 Intel，已签名并经苹果公证）或 Windows 版，需要的东西都在里面。它会找到你电脑上的 Claude Code、Codex 或 Pi，有新版本时经你同意自己更新。[下载 ↓](#开始使用)

<details>
<summary>更早</summary>

- **2026 年 10 月 14 日：直接读你的 Zotero 文献库。** 拖放框下面的 **Zotero 文献库** 按 Zotero 里的样子列出你的文献库和分类，任何条目点一下就能打开：arXiv 上有就读 arXiv，没有就读它自己的 PDF。感谢 [@adalach](https://github.com/adalach)。[直接读你的 Zotero ↑](#直接读你的-zotero)
- **2026 年 10 月 14 日：读 arXiv 页面更安全了。** 页面里可能运行脚本的部分，会在阅读器显示之前去掉，图都保持原样。感谢 [@neil-patel77](https://github.com/neil-patel77)。
- **2026 年 10 月 13 日：把一页存成一个文件。** 阅读页顶部的 **保存** 把整页存成一个 HTML 文件，可以带上标注和原文 PDF；也可以只存标注。[保存一页 ↓](#保存一页)
- **2026 年 10 月 13 日：Word、PowerPoint、Excel、电子书等文件。** 拖入 Word、PowerPoint、Excel 文件，或 CSV、EPUB、保存的网页，马上就能打开，公式也在，不用另装任何东西。
- **2026 年 10 月 13 日：完整的图，和使用说明。** PDF 引擎拆成碎块的图，现在从原页上整幅裁出来。第一次打开会弹出一份简短的使用说明，之后可以从 **使用说明** 再打开。
- **2026 年 10 月 9 日：PaperFold 改名为 TextFold。** 还是同一个阅读器，新名字涵盖它能折叠的一切：论文、网页、PDF、README，以及 agent 的回答。旧仓库的链接会自动跳到这里，设置也会自动搬过来。
- **2026 年 10 月 9 日：任意网页和 PDF。** 粘贴任何网页的链接，就能在五个层级上读它的正文，网页对读者隐藏的文字会被去掉。拖入一个 PDF：如果它是一篇网上能读到的论文，就打开网上的版本，你的 PDF 放在旁边对照；其他 PDF 在你的电脑上转换。
- **2026 年 10 月 9 日：给 agent 用。** `python3 -m textfold get <链接> --level topic` 输出一份文档的地图，`--section` 再展开需要的那一节。[了解更多 ↓](#给-agent-和脚本用)
- **2026 年 10 月 8 日：读任何 GitHub README。** 粘贴仓库链接，就能在五个层级上读它的 README，logo、徽章和动图都和 GitHub 上一样。
- **2026 年 10 月 8 日：对照原文读。** 论文页顶部的 **原文** 会在左边打开它的 PDF，读到哪一段，就标出它在原页上的位置。新论文解析完就能打开，缩放层级在后台生成。
- **2026 年 10 月 7 日：Agent 的回答也能折叠了。** [Claude Code mod](#在-claude-code-和-pi-里) 把五个层级放到每条回答上。按 5 看一句话的答案，按 1 看每一个字。
- **2026 年 10 月 6 日：不只读 arXiv。** PubMed Central、bioRxiv、medRxiv、任何语言的维基百科，以及你自己的 Markdown 文件。

</details>

<br>

## 贡献者

<a href="https://github.com/neil-patel77" title="@neil-patel77"><img src="https://github.com/neil-patel77.png?size=80" width="40" height="40" alt="@neil-patel77" /></a>
<a href="https://github.com/adalach" title="@adalach"><img src="https://github.com/adalach.png?size=80" width="40" height="40" alt="@adalach" /></a>
<a href="https://github.com/suhyungJang" title="@suhyungJang"><img src="https://github.com/suhyungJang.png?size=80" width="40" height="40" alt="@suhyungJang" /></a>
<a href="https://github.com/sylvainHellin" title="@sylvainHellin"><img src="https://github.com/sylvainHellin.png?size=80" width="40" height="40" alt="@sylvainHellin" /></a>
<a href="https://github.com/jlamweil" title="@jlamweil"><img src="https://github.com/jlamweil.png?size=80" width="40" height="40" alt="@jlamweil" /></a>
<a href="https://github.com/lamegoat" title="@lamegoat"><img src="https://github.com/lamegoat.png?size=80" width="40" height="40" alt="@lamegoat" /></a>
<a href="https://github.com/Kullenej" title="@Kullenej"><img src="https://github.com/Kullenej.png?size=80" width="40" height="40" alt="@Kullenej" /></a>
<a href="https://github.com/666xz666" title="@666xz666"><img src="https://github.com/666xz666.png?size=80" width="40" height="40" alt="@666xz666" /></a>
<a href="https://github.com/peitianyi23-sudo" title="@peitianyi23-sudo"><img src="https://github.com/peitianyi23-sudo.png?size=80" width="40" height="40" alt="@peitianyi23-sudo" /></a>
<a href="https://github.com/mcardZH" title="@mcardZH"><img src="https://github.com/mcardZH.png?size=80" width="40" height="40" alt="@mcardZH" /></a>
<a href="https://github.com/momoko-sketch" title="@momoko-sketch"><img src="https://github.com/momoko-sketch.png?size=80" width="40" height="40" alt="@momoko-sketch" /></a>

欢迎贡献：先看 [CONTRIBUTING.md](https://github.com/chenxiachan/textfold/blob/main/CONTRIBUTING.md)。

<br>

<div align="center">

**如果 TextFold 让阅读轻松了一些，点个 ⭐ star，让更多人看到它。**

</div>

---

<div align="center">

<sub>TextFold 建立在这些开源项目之上：[trafilatura](https://github.com/adbar/trafilatura) 从网页中找出正文，[pdf-inspector](https://github.com/firecrawl/pdf-inspector) 读取 PDF 自带的文字，[PDFium](https://pdfium.googlesource.com/pdfium/)（经由 [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)）裁出图，[MinerU](https://github.com/opendatalab/MinerU) 作为 PDF 引擎转换 PDF，[mammoth](https://github.com/mwilliamson/python-mammoth) 读取 Word 文件，[PDF.js](https://github.com/mozilla/pdf.js) 显示 PDF，[KaTeX](https://katex.org) 排版公式。感谢它们的作者。</sub>

[Apache 2.0](https://github.com/chenxiachan/textfold/blob/main/LICENSE) © 2026 Xia Chen · [开发文档](https://github.com/chenxiachan/textfold/blob/main/docs/DEVELOPMENT.md) · [格式](https://github.com/chenxiachan/textfold/blob/main/docs/format.md) · [参与贡献](https://github.com/chenxiachan/textfold/blob/main/CONTRIBUTING.md) · [安全](https://github.com/chenxiachan/textfold/blob/main/SECURITY.md) · [反馈](https://github.com/chenxiachan/textfold/issues)

</div>
