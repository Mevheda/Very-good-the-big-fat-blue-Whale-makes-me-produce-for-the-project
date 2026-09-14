---
name: homework-runner
description: Install, configure, complete, or resubmit a Moodle chapter assignment from locally supplied textbook images. Use when the user sends this repository URL, asks for a chapter-specific workflow such as “do course chapter N,” or asks to verify a submission. Answers should read like a student's natural paraphrase, not a copied textbook answer.
---

# Homework Runner

## Outcome

Drive this workflow end to end:

1. Resolve the configured course and chapter.
2. Read the assignment from Moodle.
3. Rank and inspect local textbook images.
4. Write structured question and answer data.
5. Build and visually verify a DOCX.
6. Upload, submit, and independently verify the result when the user requested submission.

## Project root

Resolve paths relative to this repository. The bundled CLI is:

`scripts/homework.py`

The default config path is:

`config/config.yaml`

The config path can be overridden with the `HOMEWORK_AUTOMATION_CONFIG` environment variable or the CLI `--config` option. Never embed credentials in this file.

## Workflow

### 1. First-run onboarding or existing setup

If `config/config.yaml` does not exist, follow [onboarding.md](references/onboarding.md). Ask configuration questions directly in the user's agent chat; do not ask the user to run a `setup` command.

The onboarding flow must:

1. run `python scripts/homework.py preflight`;
2. test model image understanding with `python scripts/homework.py capability` and the probe image;
3. collect Moodle URL, credentials, and folder preference in chat;
4. run `configure`, `list-courses`, `add-course`, and `sync-course`;
5. create and optionally open the image folder;
6. report the exact image folder path.

If configuration already exists, run:

```powershell
python scripts/homework.py doctor
```

Do not continue while required packages, credentials, browser, renderer, or course mapping are missing.

### 2. Resolve the request

Map the user's course name through `courses.<key>.aliases`. Map “chapter N,” Chinese chapter numbers, or an assignment title to the numeric chapter key.

If the course or chapter is ambiguous, report the available mappings and stop. Do not guess.

If `sync-course` is needed, run:

```powershell
python scripts/homework.py sync-course --course <course-key>
```

This updates assignment module IDs and titles in the config after making a backup.

### 3. Prepare the assignment

Run:

```powershell
python scripts/homework.py prepare --course <course-key> --chapter <number>
```

Read the JSON output and use:

- `assignment_dir`
- `assignment.required_problems`
- `assignment.pages`
- `materials.candidates`

The candidate ranking uses filename matching only. Inspect image content before accepting the mapping.

### 4. Inspect images

If the user sends images directly in the chat, save the attachment files into the configured materials directory before running `prepare`. If the host agent cannot access attachment paths, ask the user for the folder path or a local image path.

Use the host agent's image-reading capability to inspect the ranked candidates. In Codex, use `view_image`.

Accept an image only when its content matches the chapter, page range, and requested problems. If any required question is missing or the image belongs to another chapter, stop and request corrected files.

### 5. Write structured data

Before writing, read:

- [data-contract.md](references/data-contract.md)
- [answer-style.md](references/answer-style.md)

Inside `assignment_dir`, replace the generated templates:

- `questions.json`
- `answers.json`

Follow [data-contract.md](references/data-contract.md) exactly.

Requirements:

- include only the requested problems;
- use real absolute image paths;
- preserve sub-question labels;
- do not leave empty text or answers;
- keep answers concise and consistent with the course materials;
- answer in natural, conversational-but-correct prose rather than textbook recitation;
- do not add deliberate mistakes, fake personal experience, or evasive wording.

### 6. Build and render

Run:

```powershell
python scripts/homework.py build --course <course-key> --chapter <number>
python scripts/homework.py render --course <course-key> --chapter <number>
```

Inspect the first, middle, and last rendered pages. Check for missing questions, incorrect headings, clipping, overlap, and broken pagination. Fix the data and rebuild before submitting.

### 7. Submit

Submit only when the user's request clearly includes submission, replacement, or resubmission.

```powershell
python scripts/homework.py submit --course <course-key> --chapter <number>
```

The command uses `submission.replace_existing` from the config. Stop if a CAPTCHA, MFA, visible consent checkbox, ambiguous confirmation, or unknown submit state appears.

### 8. Verify

Run:

```powershell
python scripts/homework.py verify --course <course-key> --chapter <number>
```

Success requires both:

- `status_submitted: true`
- `file_present: true`

Never report success from the upload click alone.

## Failure handling

- Login failure: check the configured URL, credentials, and network.
- Missing assignment mapping: run `sync-course`.
- Missing or ambiguous images: stop and ask for a better filename or image.
- DOCX failure: inspect the command output and `evidence/`.
- Unknown submission state: run `verify`; do not click submit again.

## Portability

The CLI is independent of Codex. Other agents can run the same commands and perform the image-reading and answer-writing steps with their own tools.
