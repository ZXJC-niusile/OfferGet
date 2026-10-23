# OfferGet

本地运行的求职工具：分析岗位要求、检查简历、生成 PDF、准备面试，也支持保研材料和 Offer 分析。
核心流程无需上传个人材料。

## 安装

需要 Python 3.9 或以上版本。生成 PDF 还需要 Chrome、Edge 或 Chromium。

```bash
git clone https://github.com/ZXJC-niusile/OfferGet.git
cd OfferGet
pip install -e ".[render]"
python cli.py doctor
```

导出 Word 需安装 `.[docs]`；使用 LaTeX、Typst 主题需安装相应编译器。

## 生成简历

支持 Markdown、文本和 JSON 输入，可参考 [简历示例](examples/sample_resume.md)。

```bash
# 默认使用 modern-navy，输出到桌面“个人简历”文件夹
python cli.py resume build examples/sample_resume.md

# 指定主题和页数；无法在可读范围内压到一页时会报错
python cli.py resume build examples/sample_resume.md --theme classic-tech --pages 1

# 指定输出目录
python cli.py resume build examples/sample_resume.md --output-dir output/resume
```

## 按岗位调整简历

先准备 JD 文件和个人履历，再开始分析：

```bash
python cli.py review examples/sample_ai_jd.txt --profile examples/candidate_profile_minimal.json --workspace output/job-review
```

程序会显示关键问题、修改前后和下一步命令。需要补充经历时，填写本轮提示的回答文件，再执行提示中的命令。例如：

```bash
# 请将路径替换为本轮显示的回答文件，后续轮次的文件名可能不同
python cli.py review --workspace output/job-review --answers output/job-review/answers.json
```

回答文件中的版本标识需要保留。修改履历或 JD 后，先不带 `--answers` 运行一次以刷新分析，再填写新模板；旧会话也按此方式刷新。

核对修改后，执行提示中的 `proposal accept` 命令。确认后的履历会接入后续面试，旧回答文件保留。更新材料时，已有简历默认在原输出目录覆盖；新的内容修改仍需确认。

目前自动调整包括内容排序和去除句首套语。新增经历来自用户补充，应用前需要确认。
`--verbose` 查看详情，`--json` 输出 JSON。

## 准备面试

```bash
python cli.py review --profile examples/candidate_profile_minimal.json --goal interview --workspace output/interview
```

根据当前简历中的项目和工作经历生成三类问题：个人贡献、方案选择、结果依据。有多段经历时优先覆盖不同项目，避免重复引用同一句话；方案与验证问题会按经历内容调整。可额外提供 JD；填写回答后，按提示继续，获取反馈和追问。
`--goal review` 可同时进行简历调整和面试复盘，面试题同样依据当前简历生成。

## 出错后如何继续

- 文件无法读取：检查提示中的路径、权限或占用程序，处理后重试。读取失败会停止分析。
- 回答 JSON 损坏：修复文件，或先改名备份，再运行工作区命令生成模板。
- 指定的会话丢失：恢复会话文件或修正 `--session` / `--workspace` 路径，再重试。
- 确认材料后生成或保存失败：修复报错原因后重试原命令。程序会校验材料并继续处理，不重复登记相同版本，也不清空已接续的回答。

## 岗位分析与简历检查

```bash
# 提取岗位要求
python cli.py jd decode examples/sample_ai_jd.txt

# 检查岗位匹配和技能缺口
python cli.py jd match examples/sample_ai_jd.txt --profile examples/sample_resume.md

# 检查简历结构、表达和指标
python cli.py ats audit examples/sample_resume.md --jd examples/sample_ai_jd.txt

# 导出脱敏版本
python cli.py resume build examples/sample_resume.md --anonymize strict
```

匹配分表示材料对岗位要求的覆盖程度，不预测面试或录用概率。
脱敏不能保证识别所有个人信息，分享前请检查文件内容和元数据。

## 主题

共 13 款，使用 `--theme` 选择。

| 主题 | 格式 | 风格 |
| --- | --- | --- |
| `modern-navy`（默认） | HTML/PDF | 海军蓝 |
| `classic-tech` | HTML/PDF | 经典黑白 |
| `silicon-clean` | HTML/PDF | 简洁留白 |
| `asu-dense` | HTML/PDF | 紧凑双列 |
| `sidebar-clean` | HTML/PDF | 侧栏布局 |
| `modern-corporate` | HTML/PDF | 商务风格 |
| `modern-career` | HTML/PDF | 通用职业简历 |
| `academic-postgraduate` | HTML/PDF | 中文学术简历 |
| `engineering-sb2nov` | HTML/PDF | 单列工程简历 |
| `academic-latex` | LaTeX/PDF | 原生 LaTeX |
| `academic-typst` | Typst/PDF | 原生 Typst |
| `ats-plain` | 文本/HTML/PDF | 简单文本布局 |
| `ats-docx` | Word | DOCX 文档 |

`--theme all` 批量生成 12 个 PDF 主题，Word 需单独导出。

## 其他功能

使用 `--help` 查看参数和示例：

| 功能 | 命令入口 |
| --- | --- |
| 解析履历 | `python cli.py profile parse --help` |
| 核对事实 | `python cli.py fact verify --help` |
| 对比修改 | `python cli.py diff audit --help` |
| 模拟追问 | `python cli.py defense simulate --help` |
| 保研材料检查 | `python cli.py baoyan --help` |
| Offer 分析 | `python cli.py offer --help` |
| 投递记录 | `python cli.py application --help` |

## 开发与测试

```bash
pip install -e ".[all]"

# 日常检查
python -m pytest tests -m "not browser and not package"

# 完整测试，包含真实浏览器和隔离安装
python -m pytest tests
```

CI 配置覆盖 Windows、Linux 和 Python 3.9–3.13；浏览器及隔离安装测试单独运行。具体通过情况以对应版本的运行结果为准。

视觉检查方法见 [主题 QA](docs/RESUME_THEME_QA.md)。排版结果仍需打开成品核对。

## 资料

- [示例文件](examples/)
- [项目结构](docs/ARCHITECTURE.md)
- [照片设置](docs/RESUME_PHOTO_MODES.md)
- [智能体使用说明](SKILL.md)

## 许可证

[CC BY-NC-SA 4.0](LICENSE)。
