# Third-Party Dependencies

ScriptBox ships as original application code under the [MIT License](./LICENSE).
It uses the following open-source libraries. All listed licenses are permissive
and compatible with MIT distribution.

| Package | License | Use in ScriptBox |
|---------|---------|------------------|
| [FastAPI](https://github.com/tiangolo/fastapi) | MIT | HTTP API server |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI server |
| [python-multipart](https://github.com/Kludex/python-multipart) | Apache-2.0 | PDF upload handling |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | Request/response models |
| [ReportLab](https://www.reportlab.com/devdocs/) | BSD-style | PDF export |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | PDF import parsing |

## What is not bundled

- No React, Vue, jQuery, Bootstrap, or other third-party frontend frameworks.
- No CDN-hosted JavaScript or CSS.
- No proprietary fonts beyond system / PDF-standard Courier.
- No sample screenplay PDFs or copyrighted script content in this repository.

## User content

Scripts you write or import remain your content. Only upload or import PDFs you
have the right to use. Do not commit private drafts under `drafts/` to git.
