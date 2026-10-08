# ATS Plain：单栏文字简历

ATS Plain 提供结构化 Markdown、单栏 HTML 和可选中文字的 PDF。它以清晰的
标题、正文和留白组织内容，适合偏好朴素简历的投递场景。不同招聘系统的解析
方式不同，本模板不承诺任何 ATS 通过率。

## 版式

- A4，左右 16mm、上下 15mm 页边距；续页保留相同打印边距。
- 黑色正文，10.5pt 字号、1.48 倍行高；姓名、模块与经历标题层级明确。
- 教育信息逐项排列，经历日期独立成行；长邮箱、机构名、日期和技能标签可换行。
- 单列阅读顺序，普通列表，无表格、侧栏、装饰卡片或隐藏关键词。
- 默认字体为 Arial / Helvetica，中文使用已安装的 Noto Sans CJK SC、微软雅黑
  或宋体等回退字体；最终 PDF 仍需检查字体和缺字情况。
- 保留现有照片选项；不需要照片时使用 `--no-photo`。照片只在身份信息区显示。

## 使用

```bash
python cli.py resume build /absolute/path/profile.json \
  --theme ats-plain --no-photo --output-dir /absolute/path/output
```

生成 `resume_ats_plain.md`、`resume_ats_plain.html` 和 `resume_ats_plain.pdf`。
若原输出正被其他程序占用，请以 CLI 实际返回的文件路径为准。PDF 需要可用的
Chrome、Edge 或 Chromium；渲染失败不代表 PDF 已生成。

Markdown 序列化与既有版本保持一致。本次更新只修改 HTML 视觉表现，
不改变来源资料、字段别名、脱敏流程或事实检查规则，也不新增内容映射。
应使用实际来源资料核对姓名、联系方式、学校、学位、机构、职位、日期、
技能、成绩、量化结果和职责范围；样例数据不能代替真实经历。

## 导出检查

1. 核对内容与来源，不把 Markdown 一致性或机器评分当成事实正确性的证明。
2. 检查每一页的可选中文字、中文字符、换行、照片、页边距和分页。
3. 保留清晰字号和完整事实，允许较长经历自然续页。
4. 在目标招聘系统中预览解析结果，再决定是否提交。

实现与验证说明见 [ATS Plain design and QA](../docs/ATS_PLAIN_DESIGN_QA.md)。
