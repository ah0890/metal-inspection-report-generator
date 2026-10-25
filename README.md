# Metal Inspection Report Generator

A local Python application for Quality Control laboratories. It turns mechanical test and metallography results into a clean, printable **one-page A4 metal inspection report** (PDF or Word).

The inspector enters the results and the acceptance criteria. **Python** compares each result with its criterion and works out the overall result. **Claude** (Anthropic API) can optionally reword rough notes into concise, professional text. Claude never makes a PASS/FAIL decision.

---

## Features

- **Saved defaults.** Units, test methods and standards, metallography conventions, recurring header details and acceptance limits are saved once in **Settings / Edit Defaults**. Every new report uses them automatically, so routine work is just identification details plus readings.
- **Quick data entry.** The main form asks only for the report number, date, material and grade, heat/batch and sample number, and the readings: yield strength, UTS, elongation, hardness readings, grain size and microstructure observation. The saved unit is shown next to each field.
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
- **Official covering letter.** Every submission can include a formal letter on your company letterhead, enclosing one or more inspection reports. The letter comes as a PDF and a Word file, separate from the report so each can be signed on its own. **Generate Complete Submission Package** produces every PDF and Word file plus a ZIP.
- **Letter history.** Finalized letters are kept with a snapshot of their enclosed reports. They can be reopened and regenerated, and are never silently overwritten.
- **Works without an API key.** Everything except AI wording runs offline, including the standard covering letter.

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

**One-time setup:** open **⚙️ Settings / Edit Defaults** and check the units, test methods and standards, metallography settings, header details and acceptance limits. Click **Save defaults**. You only need to come back here when something changes.

**Routine inspection:**

1. Open the application. A new report starts with your saved defaults.
2. Enter the identification details: report number, date, material, and grade, heat/batch and sample number if needed.
3. Enter the readings: yield strength, UTS, elongation, hardness readings (the average is calculated for you), grain size and microstructure observation.
4. Click **Generate PDF** or **Generate Word Report** at the bottom of the same tab. Python validates the readings, evaluates them against the saved acceptance criteria, and builds the one-page report. It is saved to **Report History** automatically.
5. Optional: in **AI Summary**, click **Generate AI Summary** to have Claude reword your notes, then review the text before generating the report.
6. Open **3 · Covering Letter** to prepare the official covering letter and the complete submission package (see [Covering letters](#covering-letters)).

Specimen IDs, preparation remarks and general remarks are under **Optional details** in the inspection tab. The **Applied settings** panel shows exactly which limits and standards will be printed.

To try the app without your own data, click **Load Sample Data** in the sidebar.

With the sample data, every test and the overall result are **PASS**: YS 275 MPa ≥ 250, UTS 325 MPa ≥ 300, elongation 12.4 % ≥ 10, hardness 82 HB within 70–90, grain size No. 8, which is No. 7 or finer.

## Covering letters

**One-time setup:** in **⚙️ Settings / Edit Defaults → Company letterhead**, check the company name, which defaults to *AH Precision Inspection & Testing Services*, and the tagline. Add an address, telephone, email, website, logo and the General Manager's name if you want them on the letterhead, then click **Save letterhead**. Anything left blank is simply left off the letterhead.

**For each submission:**

1. Generate the inspection report(s) as usual. For several samples or batches under one submission, generate each report and click **New Report** in between.
2. Open **3 · Covering Letter**. Select the enclosed reports, or click **Add current report**. The enclosure order is the order you select them in.
3. Enter the letter details:
   - **Required:** letter number and recipient organization. The date defaults to today.
   - **Optional:** recipient department, name and address; project name and reference; indenter or requesting organization (PCSIR, a client, a project office, anything); sample submission reference; receipt date; number of samples; and the person the reports are finally forwarded to.
   - Fields with a **previously used** picker let you reuse organizations and project details from earlier letters.
4. Review the letter in the preview box. Fields you leave blank are filled automatically from the enclosed reports:
   - report numbers and enclosure list
   - material and grade
   - sample numbers and heat/batch numbers
   - inspection/testing dates (taken from the report dates)
   - indenter (taken from the report's customer)

   Anything you type takes precedence. Sentences whose details are missing are left out; nothing is invented.
5. Optional: under **Edit or improve the wording**, copy the standard wording and edit it, or click **Improve wording with Claude** (needs an API key) and review the result. The letterhead, reference number, date, recipient, subject and enclosure list are always generated by the application and are never changed by AI. If edited wording mentions results ("passed", "conforming", …), you get a warning, because the letter should not state outcomes.
6. Click **Generate Complete Submission Package**. This gives you:
   - every enclosed inspection report as PDF and Word
   - the covering letter as PDF and Word
   - a ZIP with all the files

   The letter is recorded as **FINAL**. Use **Generate Covering Letter (PDF + Word)** or **Save draft** to produce drafts first.
7. Print the letter and reports, then send them to the General Manager for signature and onward submission.

**History and integrity:**

- **Storage:** letters live in a `letters` table in the same database.
- **Snapshots:** a FINAL letter keeps a copy of its enclosed reports and of the letterhead as they were when it was finalized. **Regenerate its documents** in Letter History reproduces exactly that version, even if a report or the letterhead changes later.
- **No silent overwrites:** saving or finalizing a letter under the number of a FINAL letter is refused. **Start a revision** proposes a new number such as `AHP/2026/001-R1`.
- **Separate numbers:** the letter number is kept separate from the inspection report numbers.

## Saved defaults

- **Where they are stored:** a `settings` table in the same SQLite database as the report history (`data/reports.db`), so they survive restarts.
- **What is saved:**
  - result units (yield, UTS, gauge length, temperature) and the hardness scale
  - gauge length and test temperature
  - tensile and hardness test methods and standards, and the hardness load/indenter
  - grain size method, etchant and magnification
  - customer, inspector, specification and drawing number
  - all acceptance limits, with their units, mandatory flags and source
  - the default number of hardness readings

  Measured values, observations, specimen IDs and remarks are **never** saved as defaults.
- **First run:** if no defaults have been saved yet, they are taken from the most recent non-sample report in the history. Any setting that report did not contain is listed as **"Not set"** on the Settings page rather than guessed.
- **Changes:** defaults change only when you click **Save defaults**. Generating a report never changes them. You can also copy the settings of any report in the history into the Settings form and then save them.
- **Old reports:** a report reopened from history keeps the units, standards and limits it was created with, so it is never quietly re-evaluated against new limits. The **Applied settings** panel has a **Use the saved defaults instead** button if you want to switch a reopened report to the current defaults. Sample data likewise keeps its own sample criteria.

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
│   └── database.py             # SQLite report history, covering letters, settings
├── models/
│   ├── inspection.py           # dataclasses: report, tests, criteria, AI text
│   ├── defaults.py             # which fields are reusable defaults; extract/apply/missing
│   ├── letter.py               # covering letter + company letterhead dataclasses
│   ├── evaluation.py           # Status / OverallResult / evaluation result types
│   └── sample_data.py          # SAMPLE DATA report
├── services/
│   ├── calculation_service.py  # deterministic PASS/FAIL logic (no AI)
│   ├── validation_service.py   # input validation (errors and warnings)
│   ├── defaults_service.py     # load / save defaults (first run: from latest real report)
│   ├── claude_service.py       # Claude wording only, with strict no-invention prompt
│   ├── report_service.py       # validate -> evaluate -> render -> save to history
│   ├── letter_service.py       # letterhead, letter validation, documents, package/ZIP, finalize
│   └── formatting.py           # shared number/requirement formatting
├── reports/
│   ├── content.py              # WHAT goes on the report (shared by PDF and DOCX)
│   ├── pdf_generator.py        # HOW the PDF looks (ReportLab Platypus, one-page fitting)
│   ├── docx_generator.py       # HOW the Word report looks (python-docx)
│   ├── letter_content.py       # WHAT the covering letter says (deterministic wording)
│   ├── letter_pdf.py           # HOW the letter PDF looks (letterhead, margins, signature)
│   └── letter_docx.py          # HOW the letter Word file looks
├── ui/                         # inspection, AI summary, covering letter, history, settings, state
└── tests/                      # pytest suite
```

**Changing the report template:** edit [reports/content.py](reports/content.py) to change which rows and labels appear in both formats. Edit [reports/pdf_generator.py](reports/pdf_generator.py) for colours, fonts, column widths and spacing; the palette and widths are constants at the top of the file. Header and footer branding come from `config/settings.py` and `.env`.

**Changing the covering letter:** edit the wording in [reports/letter_content.py](reports/letter_content.py). Edit [reports/letter_pdf.py](reports/letter_pdf.py) and [reports/letter_docx.py](reports/letter_docx.py) for the letterhead, margins, typography and signature block. These files are independent of the inspection report template.

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
- saved defaults
- covering letters:
  - wording built only from data that was provided, with recipients and indenters entered per letter rather than built in
  - no outcome statements
  - one-page PDF and DOCX output
  - multiple reports in one letter, with matching enclosure lists
  - the complete package and ZIP
  - finalized letters preserved, never overwritten, and keeping their report snapshots

## Safety and engineering limitations

- **Acceptance criteria always come from you.** The application has no built-in material specifications and never infers a limit from a material or grade name. Check criteria against the governing document. The "source of acceptance criteria" field records where they came from.
- **No unit or hardness-scale conversion is done.** If units differ, the test is marked for review.
- **Claude only writes wording.** It receives the statuses already calculated by Python and is told not to invent results, standards or criteria, and not to contradict the statuses. AI text can still contain mistakes, so the inspector must review and edit it before release. When AI wording is used, the report footer says so.
- **Validation checks plausibility, not correctness.** It rejects impossible input such as negative values or min > max, but cannot detect a wrongly transcribed result.
- **The overall result supports, but does not replace, the reviewer.** The report has Inspected By and Reviewed By signature blocks for formal release.
- The report fits on one page within the built-in text limits. If a page overflow ever happens, the app warns you.
- The Word report uses compact margins and normally fits on one page. Its final layout depends on the word processor and fonts installed.
