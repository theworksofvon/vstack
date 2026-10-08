# Guided Review HTTP API

Use this API when the `guided-review` MCP server is not among your tools. It
does the same work as the MCP tools. Send `Content-Type: application/json` on
every write.

| MCP tool         | Request                                                                         | Body                                                                          |
| ---------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `get_review`     | `GET /api/sessions/<id>`                                                        | none                                                                          |
| `get_focus`      | `GET /api/focus`                                                                | none                                                                          |
| `set_verdict`    | `PUT /api/sessions/<id>/findings/<findingId>`                                   | `{"verdict":"agree"\|"disagree"\|"unsure"\|null,"note":"<their reason>"}`     |
| `add_comment`    | `POST /api/sessions/<id>/comments`                                              | `{"path":"<file in the PR>","line":<right-side line>,"body":"<their words>"}` |
| `delete_comment` | `DELETE /api/sessions/<id>/comments/<commentId>`                                | none                                                                          |
| `mark_reviewed`  | `PUT /api/sessions/<id>/chapters/<chapterId>` or `PUT /api/sessions/<id>/files` | `{"reviewed":true}`, or `{"path":"<file>","viewed":true}`                     |

Each write returns `{ human }`, the user's state after the write. The page
shows the write at once.
