# OfferGet

[English (Primary)](README.md) | **简体中文**

本地简历制作 Skill（[`SKILL.md`](SKILL.md)）与 Python CLI，用于整理个人资料、定制简历和导出文件。所有 CLI 命令均在本地运行，无需上传个人材料或调用付费模型 API。

## 安装

需要 Python 3.9 或以上版本。生成 PDF 还需要 Chrome、Edge 或 Chromium。

```bash
git clone https://github.com/ZXJC-niusile/OfferGet.git
cd OfferGet
pip install -e ".[render]"
python cli.py doctor
```

- 支持的输入格式：`.md`、`.txt`、`.docx`、`.html`、`.pdf`、`.json`（解析时还支持 `.bib`）；导出格式：PDF、HTML、DOCX、TeX、Typst。
- 导出或解析 Word（`.docx`）需安装 `.[docs]`（开发与运行完整测试可安装 `pip install -e ".[all]"`）。
- 原生学术排版需要安装 `xelatex`（`academic-latex`）或 `typst` Python 包 / CLI（`academic-typst`）；当本机缺少原生编译器时，会自动回退至共用的学术 HTML 预览与浏览器渲染链路。
- 请在仓库根目录运行命令，含空格的路径请加引号。

## 选择流程

| 流程 | 已有材料 | 得到什么 |
| --- | --- | --- |
| [A. 整理资料](#a-整理资料) | 零散笔记、旧简历、BibTeX 文献或项目文档 | 核对过的可复用 JSON 底稿 |
| [B. 现有资料编译](#b-现有资料编译) | 已整理的简历或 JSON 底稿 | 排版后的简历文件 |
| [C. 全流程定制](#c-全流程定制) | 已核对的个人底稿和目标岗位 JD（文字或截图） | 对话确认后的改写稿、事实与差异核查报告及成品简历 |

按需选择即可：单纯排版不要求提供 JD；单独的核查需求（`ats audit`、`fact verify`、`diff audit`、`resume audit`）可直接按需调用。下方命令使用虚构示例，实际使用时请替换为自己的文件路径。

## A. 整理资料

1. 将教育、工作、项目、个人职责、量化成果、技能和论文整理成 Markdown 底稿或结构化 JSON 档案。学术 CV 请保留准确的作者顺序、本人姓名加粗信息、发表状态（`published`、`accepted`、`under_review`、`submitted`）及论文链接。
2. 可直接把已有简历或 `.bib` 解析为独立的 JSON 底稿，不改动原文件：

```bash
python cli.py profile parse examples/sample_resume.md --output output/profile.json
```

3. 检查识别出的章节、警告和未归类原文，对照原始材料修正后再记录核对状态：

```bash
python cli.py profile parse output/profile.json --confirm-parsed --output output/reviewed-profile.json
```

4. 私有项目笔记、设计文档或故障复盘可通过 `profile refs` 在本地分块检索（结果带 `reference-only` 标记，仅用于回忆细节与核对，不直接写入公开简历）：

```bash
python cli.py profile refs --docs notes/ --query "distributed cache latency" --limit 5 --json
```

`--confirm-parsed` 仅记录你已人工核对解析结果，不代表外部事实核验。档案条目支持可见性标记（`always`、`variant-specific`、`on-request`、`reference-only`）；公开导出要求使用仅含 `always` 条目的安全公开底稿，未决的可见性标记会被拒绝导出。结构可参考[精简资料示例](examples/candidate_profile_minimal.json)与[完整资料示例](examples/candidate_profile.json)。

## B. 现有资料编译

输入已整理的简历文件或核对过的 JSON 底稿。文本导入采用确定性规则解析，正式分享前请检查是否完整保留了原始事实。

```bash
# 默认 modern-navy 主题（CLI 默认启用 --no-photo 与 --pages auto）
python cli.py resume build examples/sample_resume.md --output-dir output/resume

# 使用核对过的 JSON 底稿指定主题与单页上限
python cli.py resume build output/reviewed-profile.json --theme classic-tech --pages 1 --output-dir output/resume
```

打开返回的文件，检查文字、链接、分页、截断和照片位置。不指定 `--output-dir` 时，默认输出到桌面“个人简历”文件夹。

| 参数 | 用途 |
| --- | --- |
| `--theme <name>` | 选择主题或格式（默认 `modern-navy`；`ats-docx` 导出 Word；`all` 生成 13 款 PDF 主题） |
| `--pages <auto\|1\|2>` | 页数预算（默认 `auto`；`1` 或 `2` 限制 PDF 页数上限） |
| `--photo-path` / `--photo-mode` | 照片处理（默认不放照片；详见 `--help` 与[照片模式说明](docs/RESUME_PHOTO_MODES.md)） |
| `--anonymize strict` | 生成脱敏导出，并省略差异侧车文件与含真实姓名的副本 |

## C. 全流程定制

1. **阅读底稿与岗位 JD**：读取已核对底稿与目标 JD 文字或截图（截图中被截断或看不清的要求需先向用户确认）。需要时可运行 ATS 结构与关键词覆盖检查：

```bash
python cli.py ats audit output/reviewed-profile.json --jd examples/sample_ai_jd.txt --json
python cli.py ats ledger output/reviewed-profile.json --jd examples/sample_ai_jd.txt --json
```

2. **展示修改建议并对话确认**：先向用户展示拟改写前后对照与证据缺口，经明确确认后再保存至**独立的修改稿文件**（如 `output/tailored.json`），保持原始底稿不变。
3. **事实、差异与公开范围检查后再渲染**：

```bash
python cli.py fact verify output/tailored.json --profile output/reviewed-profile.json --json
python cli.py diff audit output/reviewed-profile.json output/tailored.json --output-dir output/diff
python cli.py resume build output/tailored.json --no-photo --baseline output/reviewed-profile.json --output-dir output/resume
```

确认修改后保存至独立修改稿（保持原始底稿不变），再运行 `fact verify`、`diff audit` 核查，并检查最终导出页面。

## 模板仍在持续优化

字体、留白、分页和不同主题之间的一致性尚在持续调整，正式投递前请务必打开成品检查。

目前共 14 款主题，通过 `--theme` 选择：

| 主题 | 格式 / 风格 |
| --- | --- |
| `modern-navy`（默认） | HTML/PDF，海军蓝左侧分栏布局 |
| `classic-tech` | HTML/PDF，经典黑白日期轨布局 |
| `asu-dense` | HTML/PDF，高密度紧凑布局 |
| `modern-corporate` | HTML/PDF，深青色商务布局 |
| `modern-career` | HTML/PDF，通用职业简历 |
| `academic-postgraduate` | HTML/PDF，中文学术 / 保研深造简历 |
| `engineering-sb2nov` | HTML/PDF，单列工程简历 |
| `executive-mckinsey` | HTML/PDF，咨询风格 |
| `awesome-cv` | HTML/PDF，红色重点标记 |
| `wall-street-classic` | HTML/PDF，紧凑衬线金融风格 |
| `ats-plain` | Markdown/HTML/PDF，单列纯文本 ATS 友好布局 |
| `academic-latex` | 原生 XeLaTeX（`.tex`）+ 独立学术 HTML + PDF |
| `academic-typst` | 原生 Typst（`.typ`）+ PDF（带共享学术 HTML 回退） |
| `ats-docx` | 原生 Word（`.docx`） |

参见[主题与格式 QA](docs/RESUME_THEME_QA.md)、[学术 LaTeX QA](docs/ACADEMIC_LATEX_LAYOUT.md)、[学术 Typst QA](docs/ACADEMIC_TYPST_LAYOUT.md)、[ATS Plain QA](docs/ATS_PLAIN_DESIGN_QA.md)、[ATS DOCX QA](docs/ATS_DOCX_LAYOUT.md) 及[照片模式说明](docs/RESUME_PHOTO_MODES.md)。

## 命令与测试

可用 CLI 命令：`profile`（`parse`、`refs`）、`resume`（`build`、`render`、`autofit`、`audit`）、`ats`（`audit`、`ledger`、`filter`）、`fact`（`verify`）、`diff`（`audit`）、`anon`（`mask`、`unmask`）、`doctor`、`selftest`。运行 `python cli.py <command> --help` 查看完整参数。

```bash
python -m pytest tests -m "not browser and not package" --strict-markers
```

浏览器/打包回归测试与专项格式 QA 命令见[发布验证](docs/RELEASE_VERIFICATION.md)，Skill 评估命令见[Skill 评估](docs/SKILL_EVALUATION.md)。

[示例文件](examples/) · [架构规范](docs/ARCHITECTURE.md) · [发布验证](docs/RELEASE_VERIFICATION.md) · [Skill 评估](docs/SKILL_EVALUATION.md) · [智能体说明](SKILL.md) · [许可证：CC BY-NC-SA 4.0](LICENSE)
