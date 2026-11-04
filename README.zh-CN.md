# OfferGet

[English（主文档）](README.md) | **简体中文**

本地运行的求职工具，用于整理资料、生成简历、按岗位调整内容和练习面试。核心 CLI 使用本地规则，无需上传个人材料或调用付费模型 API。

## 安装

需要 Python 3.9 或以上版本。生成 PDF 还需要 Chrome、Edge 或 Chromium。

```bash
git clone https://github.com/ZXJC-niusile/OfferGet.git
cd OfferGet
pip install -e ".[render]"
python cli.py doctor
```

导出 Word 还需安装 `.[docs]`；使用原生 LaTeX、Typst 输出需安装相应编译器。命令在仓库根目录运行，含空格的路径加引号。

## 选择流程

| 流程 | 已有材料 | 得到什么 |
| --- | --- | --- |
| [A. 整理资料](#a-整理资料) | 零散笔记、旧简历、项目记录、论文信息 | 核对过的可复用底稿 |
| [B. 现有资料编译](#b-现有资料编译) | 已整理的 Markdown、文本或 JSON 简历 | 排版后的简历文件 |
| [C. 全流程](#c-全流程) | 个人资料和目标岗位 JD | 内容调整、确认导出和面试练习 |

按需要选择即可。单纯排版不要求提供 JD，也不必先做面试。下方命令使用虚构示例，实际使用时替换为自己的文件路径。

## A. 整理资料

1. 将教育、工作、项目、个人职责、成果、技能和论文整理成 Markdown 底稿。经历与对应成果放在一起；科研项目按研究问题、方法、个人贡献、实验结果展开，保留作者顺序和发表状态。
2. 补充可核对的仓库、已合并 PR、论文、报告或测量记录，处理日期与指标冲突。CLI 只解析输入文件，**不会自动检索 GitHub 或补全缺失事实**；资料检索和实质改写需要另行阅读来源、核对内容。
3. 将底稿解析到独立的 JSON 文件：

```bash
python cli.py profile parse examples/sample_resume.md --output output/profile.json
```

检查识别结果、警告和未归类原文，按原始资料修正 JSON。核对后再记录确认状态：

```bash
python cli.py profile parse output/profile.json --confirm-parsed --output output/reviewed-profile.json
```

`--confirm-parsed` 仅记录你核对过解析结果，不代表外部事实已验证。内部证据和待确认事项保留在总档案中，导出使用仅含允许公开内容的独立底稿。结构可参考[个人资料示例](examples/candidate_profile_minimal.json)。

**下一步：**将核对后的底稿用于流程 B 或 C。只整理资料时，不必生成简历。

## B. 现有资料编译

输入已整理的 `.md`、`.txt` 或 `.json` 文件。文本导入采用规则解析，分享前先检查是否保留了原始事实。

```bash
# 默认 modern-navy 主题，生成一份简历
python cli.py resume build examples/sample_resume.md --output-dir output/resume

# 用核对过的 JSON 底稿选择其他主题
python cli.py resume build output/reviewed-profile.json --theme classic-tech --output-dir output/resume
```

打开返回的文件，检查文字、链接、分页、截断和照片位置。不指定 `--output-dir` 时，输出到桌面“个人简历”文件夹。

| 参数 | 用途 |
| --- | --- |
| `--pages auto` | 默认页数处理 |
| `--pages 1` / `--pages 2` | 指定 PDF 页数上限，成品超出时会报错 |
| `--photo-path "photo.jpg"` | 使用本地照片 |
| `--no-photo` | 不放照片，也不预留照片位 |
| `--theme ats-docx` | 导出 Word，保留默认 `--pages auto` |
| `--theme all` | 批量生成 13 款 PDF 供比较，Word 单独导出 |
| `--anonymize strict` | 生成脱敏版本，分享前仍需检查 |

这条流程用于排版已有内容，不会编造成果，也不代表已对照外部来源核实经历。

## C. 全流程

### 1. 准备底稿和岗位

使用流程 A 的已核对底稿，或自己已有的可靠资料，将目标岗位 JD 保存为文本文件。

```bash
python cli.py review examples/sample_ai_jd.txt --profile output/reviewed-profile.json --goal review --workspace output/job-review
```

工作目录关联原始路径、会话、回答模板、提案和输出文件。只想调整简历时，将目标换成 `--goal tailor`。

### 2. 补充事实与证据

阅读问题和修改预览。需要补充信息时，填写本轮提示的回答文件，再执行提示中的下一步命令。首轮可能是：

```bash
python cli.py review --workspace output/job-review --answers output/job-review/answers.json
```

保留回答模板中的版本标识。后续轮次文件名可能变化，以**本轮实际显示的路径**为准。修改底稿或 JD 后，先不提交旧回答，刷新一次：

```bash
python cli.py review --workspace output/job-review
```

材料未变时，续填回答会复用已有岗位解码和匹配结果。

### 3. 确认修改并导出

核对修改前后内容，同意后执行程序显示的完整 `proposal accept` 命令，其中包含本轮提案 ID、源文件、JD、数据库、工作目录和导出参数。没有待确认修改时，按提示直接导出。

内容修改需确认。目前自动调整包括相关性排序和去除句首套语，新增事实来自你提供的材料。确认后的履历会接入后续面试。源材料更新时，已有简历在配置的输出目录刷新；需要历史成品时，请另存副本。

### 4. 根据当前简历练习面试

在同一工作目录继续：

```bash
python cli.py review --workspace output/job-review --goal interview
```

也可以跳过岗位调整，直接以简历开始，不要求 JD：

```bash
python cli.py review --profile examples/candidate_profile_minimal.json --goal interview --workspace output/interview
```

问题围绕当前简历中的个人贡献、方案选择和结果依据。填写显示的回答模板，再按提示获取反馈与追问。独立面试不创建材料提案，也不导出简历。

`--verbose` 展开详情，`--json` 输出结构化结果。匹配分表示材料对岗位要求的覆盖程度，不预测面试或录用概率。

## 模板仍在优化

**模板部分仍在持续优化。** 字体、留白、分页和不同主题的一致性尚在调整，正式投递前请打开成品检查。

目前共 14 款，通过 `--theme` 选择：

| 主题 | 格式 / 风格 |
| --- | --- |
| `modern-navy`（默认） | HTML/PDF，海军蓝 |
| `classic-tech` | HTML/PDF，经典黑白 |
| `asu-dense` | HTML/PDF，紧凑双列 |
| `modern-corporate` | HTML/PDF，商务 |
| `modern-career` | HTML/PDF，通用职业简历 |
| `academic-postgraduate` | HTML/PDF，中文学术简历 |
| `engineering-sb2nov` | HTML/PDF，单列工程简历 |
| `academic-latex` | LaTeX/PDF |
| `academic-typst` | Typst/PDF |
| `ats-plain` | 文本/HTML/PDF |
| `executive-mckinsey` | HTML/PDF，咨询风格 |
| `awesome-cv` | HTML/PDF，红色章节标记 |
| `wall-street-classic` | HTML/PDF，紧凑衬线字体 |
| `ats-docx` | Word/DOCX |

批量生成时，各主题的差异和排版报告分别保存。参见[主题 QA](docs/RESUME_THEME_QA.md)和[照片设置](docs/RESUME_PHOTO_MODES.md)。

## 出错后继续

路径、权限或文件占用问题处理后重试。回答 JSON 损坏时，修复文件或先改名备份，再生成新模板。会话丢失时，恢复文件或修正路径。确认或导出中断后，可重试原命令，恢复检查会保留已确认版本及接续后的回答。

## 其他功能与开发

用 `python cli.py --help` 或具体命令的 `--help` 查看岗位分析（`jd`）、简历检查（`ats`）、事实与差异检查（`fact`、`diff`）、保研材料（`baoyan`）、Offer 分析（`offer`）和投递记录（`application`）。

```bash
pip install -e ".[all]"
python -m pytest tests -m "not browser and not package"
# 完整测试，包含真实浏览器与隔离安装
python -m pytest tests
```

日常 CI 使用 Linux/Python 3.9、Linux/Python 3.13 和 Windows/Python 3.13，浏览器及安装包检查单独运行。手动开启 `full-matrix` 可检查两个平台的 Python 3.9–3.13；通过情况以实际运行结果为准。

[示例文件](examples/) · [项目结构](docs/ARCHITECTURE.md) · [智能体说明](SKILL.md) · [许可证：CC BY-NC-SA 4.0](LICENSE)
