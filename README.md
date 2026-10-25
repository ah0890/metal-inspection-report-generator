# Metal Inspection Report Generator

A local Python application for Quality Control laboratories. It turns mechanical test and metallography results into a clean, printable **one-page A4 metal inspection report** (PDF or Word).

The inspector enters the results and the acceptance criteria. **Python** compares each result with its criterion and works out the overall result. **Claude** (Anthropic API) can optionally reword rough notes into concise, professional text. Claude never makes a PASS/FAIL decision.

---

## Features

- **Structured data entry** in a Streamlit interface: inspection information, tensile test, hardness test, metallography, acceptance criteria.
- **No assumed units.** Every value needs an explicitly selected unit or scale (MPa, N/mm², ksi, psi; HB, HBW, HRA, HRB, HRC, HV, HK).
- **Multiple hardness readings**, with the average calculated automatically.
- **Deterministic evaluation.** Minimum, maximum and range criteria are checked in plain Python, and the boundaries count as passing.
  - Each test gets a status: `PASS`, `FAIL`, `REVIEW` (criterion present but no result, or units that don't match) or `NOT EVALUATED` (no criterion).
  - The overall result is `PASS`, `FAIL` or `REVIEW REQUIRED`.
- **No invented requirements.** If no criterion is entered, the report says *"Acceptance criterion not specified"*.
- **AI-assisted wording** (optional). Claude writes a short inspection summary and professional microstructure and remarks text. You can edit all of it before it goes on the report.
- **Professional one-page PDF** built with ReportLab Platypus. If the content is too long, the typography is tightened automatically so the report stays on one page.
- **Word (DOCX) output** with the same layout.
- **Report history** in SQLite. You can search by report number, material or heat/batch, reopen a report in the form, regenerate its PDF, or delete it.
- **Sample data** loads with one click, is clearly marked SAMPLE DATA, and is watermarked on the report.
- **Validation.** Negative values, missing units, min > max, and missing report number, material or date are rejected. Missing mandatory results are flagged.
- **Works without an API key.** Everything except AI wording runs offline.

## Requirements

- **Python 3.10 or newer** (tested on Python 3.14)
- An Anthropic API key, only if you want AI wording

## Installation

```bash
git clone https://github.com/ah0890/metal-inspection-report-generator.git
cd metal-inspection-report-generator

# (recommended) create a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Environment setup and Anthropic API key

1. Create an API key in the [Anthropic Console](https://console.anthropic.com/).
2. Copy the example environment file and add your key:

   ```bash
   cp .env.example .env        # Windows: copy .env.example .env
   ```

   ```dotenv
   ANTHROPIC_API_KEY=your_api_key_here
   ```

   You can also set `ANTHROPIC_API_KEY` as an ordinary environment variable.

`.env` is listed in `.gitignore` and must never be committed. The key is read only from the environment. It is never hard-coded, never saved in the report history database and never written into reports.

Optional settings in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `MIRG_LAB_NAME` | `Quality Control Laboratory` | Laboratory name in the report header |
| `MIRG_LAB_SUBTITLE` | `Mechanical Testing & Metallography` | Header subtitle |
| `MIRG_FORM_NUMBER` | `QC-MIR-01 Rev. 0` | Document-control number in the footer |
| `MIRG_CLAUDE_MODEL` | `claude-opus-5-5` | Claude model used for wording |
| `MIRG_CLAUDE_EFFORT` | `low` | Claude effort level (`low` … `max`) |
| `MIRG_DATABASE_PATH` | `data/reports.db` | Location of the report history database |

## Running the application

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit opens the app in your browser (default http://localhost:8501).

## Example workflow

1. Open the application. Click **Load Sample Data** in the sidebar to try it straight away, or **New Report** to start from a blank form.
2. **Inspection Information**: report number, date, customer, material, grade, heat/batch, sample number, drawing and specification, inspector, remarks.
3. **Mechanical Testing**: yield strength, UTS and elongation, with units, gauge length, specimen ID, temperature and method. Then the hardness scale and readings; the average is calculated for you.
4. **Metallography**: grain size number and method, etchant, magnification, specimen ID, microstructure observation, preparation remarks.
5. **Acceptance Criteria**: enter min/max limits from the governing specification and the source of those criteria. Tick **Mandatory** for each test that must pass.
6. Click **Evaluate**. Python calculates each test's status and the overall result.
7. **AI Summary**: click **Generate AI Summary**. Claude rewrites your notes, and you review and edit the text.
8. **Generate Report**: click **Generate PDF** or **Generate Word Report**, then download. The report is saved to **Report History** automatically.

With the sample data, every test and the overall result are **PASS**: YS 275 MPa ≥ 250, UTS 325 MPa ≥ 300, elongation 12.4 % ≥ 10, hardness 82 HB within 70–90, grain size No. 8, which is No. 7 or finer.

## How the evaluation works

All decisions are made in [services/calculation_service.py](services/calculation_service.py).

| Situation | Test status |
|---|---|
| Result meets every entered limit (limits inclusive) | `PASS` |
| Result is below the minimum or above the maximum | `FAIL` |
| Criterion entered but no result | `REVIEW` |
| Result and criterion units differ (no conversion is done) | `REVIEW` |
| No criterion entered | `NOT EVALUATED`, and the report shows "Acceptance criterion not specified" |

Grain size numbers increase as the grain gets finer, as in ASTM E112. A minimum grain size number therefore means "No. N or finer".

Overall result:

1. **FAIL** if any mandatory test fails.
2. Otherwise **REVIEW REQUIRED** if any test needs review, a mandatory test has no criterion or no result, or a non-mandatory test failed.
3. Otherwise **PASS** if at least one test was evaluated and passed.
4. **REVIEW REQUIRED** if nothing could be evaluated.

## Project architecture

```
metal-inspection-report-generator/
├── app.py                      # Streamlit entry point (sidebar + tabs)
├── requirements.txt
├── .env.example                # template for ANTHROPIC_API_KEY (copy to .env)
├── config/
│   └── settings.py             # paths, branding, units/scales, AI model, text limits
├── database/
│   └── database.py             # SQLite report history (metadata + report JSON)
├── models/
│   ├── inspection.py           # dataclasses: report, tests, criteria, AI text
│   ├── evaluation.py           # Status / OverallResult / evaluation result types
│   └── sample_data.py          # SAMPLE DATA report
├── services/
│   ├── calculation_service.py  # deterministic PASS/FAIL logic (no AI)
│   ├── validation_service.py   # input validation (errors and warnings)
│   ├── claude_service.py       # Claude wording only, with strict no-invention prompt
│   ├── report_service.py       # validate -> evaluate -> render -> save to history
│   └── formatting.py           # shared number/requirement formatting
├── reports/
│   ├── content.py              # WHAT goes on the report (shared by PDF and DOCX)
│   ├── pdf_generator.py        # HOW the PDF looks (ReportLab Platypus, one-page fitting)
│   └── docx_generator.py       # HOW the Word report looks (python-docx)
├── ui/                         # one module per tab, plus session-state mapping
└── tests/                      # pytest suite
```

**Changing the report template:** edit [reports/content.py](reports/content.py) to change which rows and labels appear in both formats. Edit [reports/pdf_generator.py](reports/pdf_generator.py) for colours, fonts, column widths and spacing; the palette and widths are constants at the top of the file. Header and footer branding come from `config/settings.py` and `.env`.

## Running the tests

```bash
pytest
```

The tests cover:

- hardness averages
- minimum, maximum and range criteria, including the boundaries
- unit mismatches
- the overall result rules
- negative values and missing required fields
- the sample data producing PASS and a one-page PDF
- the longest allowed text still fitting on one page
- searching and reopening report history
- the API key never being stored
- the clear error shown when no API key is set

## Safety and engineering limitations

- **Acceptance criteria always come from you.** The application has no built-in material specifications and never infers a limit from a material or grade name. Check criteria against the governing document. The "source of acceptance criteria" field records where they came from.
- **No unit or hardness-scale conversion is done.** If units differ, the test is marked for review.
- **Claude only writes wording.** It receives the statuses already calculated by Python and is told not to invent results, standards or criteria, and not to contradict the statuses. AI text can still contain mistakes, so the inspector must review and edit it before release. When AI wording is used, the report footer says so.
- **Validation checks plausibility, not correctness.** It rejects impossible input such as negative values or min > max, but cannot detect a wrongly transcribed result.
- **The overall result supports, but does not replace, the reviewer.** The report has Inspected By and Reviewed By signature blocks for formal release.
- The report fits on one page within the built-in text limits. If a page overflow ever happens, the app warns you.
- The Word report uses compact margins and normally fits on one page. Its final layout depends on the word processor and fonts installed.
