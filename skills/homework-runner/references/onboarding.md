# First-Run Onboarding

The user should only need to send the repository URL and answer questions in the agent chat. Do not tell the user to run `setup`.

## 1. Download and inspect

Clone or download the repository into a user-writable directory. Read:

- `AGENTS.md`
- this Skill
- `references/data-contract.md`
- `references/answer-style.md`

## 2. Preflight

Run:

```powershell
python scripts/homework.py preflight
```

Check the JSON output for Python, Git, required packages, browser, renderer, and the image probe path.

If anything is missing:

- explain the exact missing item;
- do not download or install without user approval;
- prefer an existing Edge or Chrome installation;
- if no browser is available, ask before running `python -m playwright install chromium`.

## 3. Test image understanding

Run:

```powershell
python scripts/homework.py capability
```

Read the returned `probe_image` using the host agent's image capability. The expected result is:

```text
PROBE-739; 3 blue circles; 2 red squares
```

If the image cannot be read correctly, stop and tell the user to switch to a vision-capable model or Agent. Do not continue to homework generation.

## 4. Ask in chat

Ask the user for:

1. Moodle website URL;
2. account and password;
3. the course they want to automate;
4. whether to use the default data folder or a custom folder.

Before accepting the password, warn once that messages in the chat history may
be retained. If the host Agent supports hidden terminal input, offer that as an
alternative. Continue with chat input if the user chooses it.

Default data folder:

```text
Windows: C:\Users\<user>\HomeworkAutomation
macOS/Linux: ~/HomeworkAutomation
```

Recommended course image folder:

```text
<data-dir>/materials/<course-key>/
```

The user may provide any writable folder, including a D-drive path on Windows.

## 5. Configure through the agent

Run the CLI with the answers collected in chat. Example:

```powershell
python scripts/homework.py configure ^
  --moodle-url "https://moodle.example.edu" ^
  --username "student-id" ^
  --password "password" ^
  --data-dir "C:\Users\student\HomeworkAutomation" ^
  --browser msedge
```

The CLI writes configuration and credentials outside the Git checkout. Never print the password in the final response.

Then list courses:

```powershell
python scripts/homework.py list-courses
```

Show the user the course names and IDs, ask which one to use, then add it:

```powershell
python scripts/homework.py add-course ^
  --course-key database ^
  --course-name "数据库系统原理" ^
  --course-id "11"
```

If the user chose a custom image folder:

```powershell
python scripts/homework.py folder --course database --path "D:\HomeworkImages\database" --open
```

Otherwise create/open the default:

```powershell
python scripts/homework.py folder --course database --open
```

Finally:

```powershell
python scripts/homework.py sync-course --course database
python scripts/homework.py doctor
```

## 6. Report readiness

Tell the user:

- the configuration succeeded;
- the image folder path;
- whether browser and Word rendering are ready;
- how to start an assignment:

```text
做数据库第一章作业
```

The user may also attach images directly in chat. In that case, save the images into the configured folder before running the normal workflow.
