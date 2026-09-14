# Homework Automation

一个面向 Moodle 的可移植作业自动化项目。它把本地课本题目图片、作业要求、答案数据和 Word 生成流程连接起来，并保留人工可审查的中间文件。

核心流程不依赖 Codex，也可由其他能够读取文件、执行 Shell 命令和理解图片的 Agent 使用。

## 给 Agent 的安装提示

发布到 GitHub 后，用户可以直接把仓库地址发给 Agent，并附上一句话：

```text
请下载并安装这个项目。先读取 AGENTS.md 和
skills/homework-runner/references/onboarding.md，
然后在聊天窗口询问我配置信息并完成初始化。
```

Agent 会自动检查环境、测试图片能力、询问 Moodle 地址和凭据、创建图片目录，并同步课程。

## 它能做什么

1. 登录配置好的 Moodle 网站。
2. 从课程左侧栏进入指定章节作业。
3. 读取作业标题、要求、截止时间和提交状态。
4. 从本地材料目录筛选与章节、页码和题号相关的图片。
5. 由 Agent 读取图片并生成 `questions.json` 和 `answers.json`。
6. 生成排版统一、可检查的 Word 文档。
7. 使用 Microsoft Word 或 LibreOffice 渲染 PDF/PNG 做视觉检查。
8. 可选地移除旧提交、上传新文件并提交。
9. 独立复查提交状态和文件名。

默认答题风格是“用自己的话复述”：保持概念正确，但尽量使用自然、简洁、口语化一些的中文表达，不照抄教材，也不故意写错或编造经历。

本项目不包含题目图片、账号、密码、Cookie、课程内容和任何学校内网地址。

## 项目结构

```text
homework-automation/
  skills/
    homework-runner/
      SKILL.md
      references/
        data-contract.md
  src/homework_automation/
  scripts/
    homework.py
    render_docx.py
  config/
    config.example.yaml
    credentials.example.ini
  tests/
```

`skills/homework-runner/SKILL.md` 是给 Agent 的工作说明。`scripts/homework.py` 是无界面命令行入口。

## 环境要求

- Python 3.11 或更高版本。
- Playwright 和浏览器（Edge、Chrome、Chromium 任选其一）。
- 生成 DOCX 只需要 `python-docx`。
- 渲染检查需要一个渲染器：
  - Windows：Microsoft Word，或 LibreOffice；
  - macOS/Linux：LibreOffice。
- 推荐 Windows 10/11，但不是生成 DOCX 的硬性要求。

## 安装

```powershell
git clone <你的仓库地址>
cd homework-automation

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e .
```

Windows 用户如果使用 Microsoft Word 做渲染检查，建议安装 Windows 额外依赖：

```powershell
pip install -e ".[windows]"
```

如果使用 LibreOffice 做渲染，则不需要 `pywin32`。

如果使用 Playwright 自带 Chromium，而不是系统 Edge/Chrome：

```powershell
python -m playwright install chromium
```

## Agent 对话式初次配置

推荐用户直接把 GitHub 仓库地址发给支持联网、Shell、文件读写和图片理解的 Agent，然后说：

```text
请安装并配置这个项目：<GitHub 地址>
```

Agent 会读取 `AGENTS.md` 和 `skills/homework-runner/references/onboarding.md`，然后：

1. 下载并检查项目；
2. 运行 `python scripts/homework.py preflight`；
3. 读取内置的能力测试图；
4. 在聊天窗口询问 Moodle 地址、账号、密码和课程；
5. 询问使用默认图片目录还是自定义目录；
6. 将配置和凭据写入用户目录，而不是写进 Git 仓库；
7. 登录、同步课程，并报告图片文件夹位置。

密码会由 Agent 写入本地数据目录。由于用户可能在聊天窗口输入密码，Agent
应先提醒一次聊天记录可能保留；如果宿主 Agent 支持隐藏终端输入，应优先提供这种方式。

默认数据目录：

```text
Windows: C:\Users\<用户名>\HomeworkAutomation
macOS/Linux: ~/HomeworkAutomation
```

默认图片目录：

```text
<data-dir>/materials/<course-key>/
```

用户可在聊天中指定任意可写目录。Agent 会把设置写入配置，并可通过以下命令创建或打开目录：

```powershell
python scripts/homework.py folder --course database --open
```

高级用户仍可手动编辑 [config.example.yaml](config/config.example.yaml)，但这不是必需的首次使用流程。

不要把真实配置、凭据或运行数据上传到 GitHub。`.gitignore` 已排除这些内容。

## 使用流程

### 1. 确认环境

首次配置完成后，Agent 会运行：

```powershell
python scripts/homework.py doctor
```

用户不需要自己执行这些命令。

### 2. 同步课程作业映射

首次配置课程后运行：

```powershell
homework-automation sync-course --course database
```

该命令会读取 Moodle 作业列表，更新课程各章节的 `module_id`、标题和 URL，并在修改前备份配置文件。

### 3. 准备某一章

```powershell
homework-automation prepare --course database --chapter 2
```

输出目录默认类似：

```text
data/assignments/database/chapter-02/
  assignment.json
  candidate-images.json
  questions.json
  answers.json
```

### 4. 让 Agent 读取图片并填写答案

把 `skills/homework-runner/SKILL.md` 和 `skills/homework-runner/references/data-contract.md` 提供给 Agent。Agent 应：

1. 读取 `candidate-images.json`；
2. 用自己的识图能力查看候选图片；
3. 把指定题目写入 `questions.json`；
4. 读取 `skills/homework-runner/references/answer-style.md`；
5. 按“自然复述、概念正确”的风格把答案写入 `answers.json`。

如果用户在 Agent 窗口中直接发送图片，Agent 应先把附件保存到该课程的 `materials_dir`，再读取 `candidate-images.json`。如果 Agent 无法访问聊天附件的本地路径，应明确告知用户，并让用户改用文件夹方式。

### 5. 生成和检查 Word

```powershell
homework-automation build --course database --chapter 2
homework-automation render --course database --chapter 2
```

检查 `render/` 中的 PNG。发现问题时修改 JSON 后重新运行。

### 6. 提交

确认文档无误后运行：

```powershell
homework-automation submit --course database --chapter 2
```

脚本会从课程左侧栏进入目标作业。若配置允许且已有提交，会先移除旧提交，再上传当前 DOCX。

遇到验证码、MFA、明确的学术诚信复选框或提交状态不明确时，流程会停止。

### 7. 独立验证

```powershell
homework-automation verify --course database --chapter 2
```

成功必须同时满足：

- `status_submitted: true`
- `file_present: true`

## 图片命名

所有图片可以放在同一个目录。脚本会从文件名中依次识别：

1. 中文或阿拉伯数字章节，例如 `第二章`、`第2章`、`ch02`；
2. 页码，例如 `64页`；
3. 题号。

推荐示例：

```text
第一章_30页.jpg
第二章_64页_第3题.jpg
第五章_166页_1.jpg
第十二章_352页.jpg
```

文件名只用于候选排序。Agent 必须读取图片内容后做最终判断。

## 支持其他 Agent

本项目不要求使用 Codex。任何具备以下能力的 Agent 都可以执行：

- 读取本地文件；
- 运行 Python 命令；
- 理解图片内容；
- 写入 JSON 和调用 CLI。

入口说明见：

- [Codex/AGENTS 规范](AGENTS.md)
- [通用 Skill](skills/homework-runner/SKILL.md)
- [数据格式](skills/homework-runner/references/data-contract.md)

## 安全注意事项

- 不要提交账号、密码、Cookie、浏览器配置、作业图片或生成数据。
- 不要公开学校内网地址。
- 上传前检查目标作业 ID、标题和文件。
- 提交结果不明确时先运行 `verify`，不要反复点击提交。
- 自动化操作必须符合课程平台条款和学校要求。

## 开发验证

```powershell
python -m compileall src scripts
python -m unittest discover -s tests -v
python scripts/homework.py doctor
```

## License

发布前请根据你的意愿添加 LICENSE。仓库当前不自动附带许可证，避免替作者做法律选择。
