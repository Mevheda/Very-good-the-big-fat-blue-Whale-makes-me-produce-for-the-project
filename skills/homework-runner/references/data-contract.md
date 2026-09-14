# Data Contract

## questions.json

```json
[
  {
    "id": "8",
    "text": "Describe the concept, purpose, and three elements of a data model.",
    "source_images": [
      "/absolute/path/to/chapter-01-page-30.jpg"
    ]
  }
]
```

Fields:

- `id`: problem number as a string;
- `text`: the complete recognized question;
- `source_images`: one or more absolute image paths that contain the question.

## answers.json

```json
{
  "8": [
    {
      "style": "paragraph",
      "text": "A normal answer paragraph."
    },
    {
      "style": "subheading",
      "text": "A bold answer subheading."
    },
    {
      "style": "bullet",
      "text": "A numbered point generated automatically by the DOCX builder."
    }
  ]
}
```

Supported styles:

- `paragraph`: normal justified text with a first-line indent;
- `subheading`: bold subheading;
- `bullet`: automatically numbered `1, 2, 3` list item.

## Validation

- Every `questions.json` entry must have a non-empty answer array.
- IDs must be strings.
- Image paths must exist.
- No placeholder text such as `TODO`, `待补充`, or `please fill`.
- Write answers according to [answer-style.md](answer-style.md).
