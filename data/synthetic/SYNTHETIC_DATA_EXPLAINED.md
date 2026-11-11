# Haq synthetic statements: what was made, and the generator explained from scratch

## 1. What you have

| Item | Detail |
|---|---|
| 20 PDF statements | 4 invented layouts (alpha, beta, gamma, delta) x 5 statements each, in `data/synthetic/<layout>/` |
| `expected_candidates.csv` | 640 labelled debit rows (32 per statement) |
| `MANIFEST.csv` | One row per file; `data_origin` is `synthetic`; scanner result is `yes` for all 20 |
| `generate_synthetic.py` | Re-creates everything; fixed seed `20261111`, so the output is identical on every run |

Run it from the repo root with `python generate_synthetic.py` (needs `reportlab` and `pdfplumber`).

**These are fake.** Every page says SYNTHETIC TEST DATA. The layouts are invented and do not copy any real bank. Numbers measured on them are "synthetic-only" and must never be mixed into the real-data T2 gate.

Layout quirks, on purpose: alpha and beta have ruled grids with separate debit and credit columns (beta uses different headers and date format). Gamma has no grid, one signed amount column (`Dr` and `Cr` suffixes) and narrations that wrap onto a second line. Delta has no grid, debits in brackets, and ISO dates. All four use Indian digit grouping (1,25,000.00), an opening-balance row, a repeated header on each page, and a closing-balance line.

## 2. The scenarios planted in every statement

| Scenario | What happens | `expected_label` | `is_true_failure` |
|---|---|---|---|
| `normal` | Ordinary UPI, card or PoS, ATM, NACH debits | unreversed | no |
| `upi_reversed_ontime` | UPI debit, credit with same reference next day | reversed | yes |
| `upi_reversed_late_noref` | UPI debit, credit 6 days later with a generic narration and no reference | reversed | yes |
| `upi_never_reversed` | UPI debit, nothing comes back | unreversed | yes |
| `atm_reversed` | ATM debit, reversal credit 5 days later | reversed | yes |
| `atm_never_reversed` | ATM debit, nothing comes back | unreversed | yes |
| `lookalike_credit` | UPI debit, later an unrelated salary-arrears credit of the same amount | unreversed | no |

The label file lists every debit, with `reversal_date` filled where a true reversal exists.

## 3. Three things I found that change your plan

1. **The precision target in T2 does not work as written.** A statement cannot show that a payment failed, so every ordinary successful payment also looks "unreversed". Measuring precision of "failed payments found" would always be poor. Measure instead (a) pairing accuracy: does the pairing label equal `expected_label` for each debit; and (b) how often rows with `is_true_failure = yes` appear in the candidate list the user sees, ranked or filtered by channel. Write the revised targets in `docs/decisions.md`. The late-reversed rows are the strongest claim cases because the money came back after the deadline.
2. **Your pre-commit scanner will block UPI references.** A UPI reference is 12 digits, the same shape as an Aadhaar number, and also falls inside the 9 to 18 digit account-number rule. The generator's scanner ignores 12 digits that sit between slashes and still flags grouped Aadhaar (4-4-4), PAN, emails, 10-digit phone numbers and other long digit runs. Copy that logic.
3. **Dates run January to May 2026**, so the T3 calendar tests need a holiday file covering those months.

## 4. The generator, explained from scratch

### 4.1 Imports and constants

| Part | What it is | What breaks without it | Other options not used |
|---|---|---|---|
| `"""docstring"""` | Text in triple quotes as the first thing in a file documents it. Python ignores it when running. | Nothing breaks; readers lose the context. | none |
| `import csv` | Loads Python's built-in CSV module so the whole name `csv` is available. | `csv.writer` fails with `NameError`. | `import csv as c` renames it |
| `from datetime import date, timedelta` | Loads two named things from the module: `date` (a calendar day) and `timedelta` (a length of time). | Date arithmetic fails. | `datetime` class adds hours, minutes, time zones; unused on purpose |
| `from pathlib import Path` | `Path` represents a file location and works the same on Windows and Linux. | You would build paths with fragile string joins. | none |
| `import re` | Regular expressions: pattern matching on text. | The scanner fails. | none |
| `import pdfplumber` | Reads text out of PDFs. | `scan_pdf` fails. | none |
| `from reportlab...` imports | `colors` (named colours), `A4` (page size in points), `ParagraphStyle` and `getSampleStyleSheet` (text styles), `Paragraph`, `SimpleDocTemplate`, `Spacer`, `Table`, `TableStyle` (building blocks for the page). | The PDF cannot be built. | `letter` page size, `PageBreak`, `Image` exist but are not used |
| `OUT = Path("data/synthetic")` | `=` stores a value under a name. Capital letters are a convention for a constant. | The output location would be repeated in many places. | `Path.home()`, `Path.cwd()` for other bases |
| `MERCHANTS = [...]` | A list: ordered items in square brackets. All names are made up. | Normal transactions would have no counterparties. | a tuple `(...)` would work too |
| `LAYOUTS = {...}` | A dictionary: `"key": value` pairs in braces. Each layout holds its date format, column style, whether to draw a grid, the header text and the column widths in points. | Four layouts cannot be described in data; you would copy the code four times. | none |
| `SCAN_PATTERNS = {...}` | Name-to-regex dictionary. `\b` is a word edge; `\d` a digit; `{9,18}` means 9 to 18 of them; `[A-Z]` a capital letter; `[6-9]` a digit 6 to 9. The `r"..."` prefix is a raw string so backslashes are kept literally. | Without `r`, `\b` would turn into a backspace character and the patterns would never match. | flags such as `re.IGNORECASE` could be added |

### 4.2 Helper functions

| Part | What it is | What breaks without it | Other options not used |
|---|---|---|---|
| `def fmt_money(paise):` | `def` defines a function; `paise` is its one required parameter. Money is whole paise so there are no rounding errors. | Amounts print as `283200` instead of `2,832.00`. | none |
| `rupees, rest = divmod(paise, 100)` | `divmod(a, b)` returns whole quotient and remainder together; the two names unpack them. | You would write `//` and `%` separately. | none |
| `digits = str(rupees)` | `str()` turns a number into text so it can be cut. | Slicing fails on a number. | `str(object, encoding, errors)` extras only for bytes |
| `if len(digits) > 3:` | `len()` counts characters; `if` runs the block only when true. | Small amounts would get stray commas. | `elif` and `else` branches not needed here |
| `head, tail = digits[:-3], digits[-3:]` | Slicing: `[:-3]` is everything except the last 3; `[-3:]` is the last 3. | The Indian rule (last three digits, then pairs) cannot be applied. | `[start:stop:step]` has an optional step |
| `while len(head) > 2:` | `while` repeats the block as long as the test is true. | Long amounts would not be split into pairs. | `break` and `continue` not used |
| `parts.insert(0, head[-2:])` | `list.insert(position, item)` puts the pair at the front. | Groups would come out in reverse order. | `append(item)` adds to the end |
| `",".join(parts + [tail])` | `+` joins two lists; `join` glues list items with a comma. | No commas. | none |
| `f"{digits}.{rest:02d}"` | An f-string inserts values. `:02d` means integer, at least 2 characters, padded with zeros. | `5` paise prints as `.5` not `.05`. | `:>10` aligns right; `:,` adds Western commas |
| `make_ref(rng)` | `rng` is a random generator passed in. `rng.randrange(a, b)` picks a whole number from `a` up to but not including `b`; `10**11` is 10 to the power 11. | References would not be 12 digits. | `randrange(start, stop, step)` has an optional `step` |
| `make_txn(day, narration, debit=0, ...)` | Parameters with `=` have default values and are optional. It returns a dictionary describing one transaction. | Each row would be built by hand in many places. | `**kwargs` (accept any extra named values) not used |

### 4.3 Building the data

| Part | What it is | What breaks without it |
|---|---|---|
| `failure_case(rng, start, scenario, channel, delay, with_ref)` | Makes a failed payment and, if `delay` is not 0, its reversal. `delay=0` is the never-reversed case. | The planted failures would not exist. |
| `start + timedelta(days=rng.randrange(1, 22))` | Adds a number of days to a date. Days 1 to 21 leave room for a 6-day reversal inside the 30-day statement. | A late reversal could fall outside the statement. |
| `if channel == "UPI" else "ATM WDL ..."` | A one-line conditional: value A if the test is true, otherwise value B. `==` compares; a single `=` would assign. | ATM cases would carry UPI-style narrations. |
| `rows = [make_txn(...)]` and `rows.append(...)` | Starts a list, then adds the reversal credit. | The reversal row is missing. |
| `build_events(rng, start)` | Creates the salary credit, 26 ordinary transactions (`for _ in range(26)`; `_` means the counter is ignored), then the six scenario cases. | No statement content. |
| `kind = rng.choice([...])` | Picks one item; "upi" appears three times so it is picked more often. | All kinds equally likely, which looks less realistic. |
| `if ... elif ... else` | Chooses one branch by channel type. | Every row would look the same. |
| `events += failure_case(...)` | `+=` extends the list with the items returned. | The cases are generated but never added. |
| `lookalike_credit` block | A normal debit plus an unrelated same-amount credit three days later. | You could not test false pairing. |

### 4.4 Drawing the PDF

| Part | What it is | What breaks without it | Other options not used |
|---|---|---|---|
| `def footer(canvas, doc):` | Called by ReportLab for each page. `canvas` is the page surface. `saveState()` and `restoreState()` bracket any change so it does not leak onto later drawing. `setFont(name, size)` chooses the font; `drawString(x, y, text)` writes text at a point measured from the bottom-left. | No footer; the fake label would appear only at the top. | `drawRightString`, `line`, `rect` |
| `ParagraphStyle("small", parent=..., fontSize=8, leading=10)` | Creates a style by copying a parent style and overriding values. `leading` is line spacing. | Wrapped narrations would use the larger default size. | `fontName`, `alignment`, `textColor`, `splitLongWords` (default on, which is why long references split mid-word) |
| `Paragraph(text, style)` | A block of wrapping text. | Narrations would not wrap. | `bulletText`, `encoding` |
| `Spacer(1, 12)` | Empty space: width 1, height 12 points. | Items would touch. | none |
| `[""] * (ncols - 3)` | Repeating a list: makes empty cells. `*` between a list and a number repeats it. | The opening-balance row would have the wrong number of columns. | none |
| `for t in rows:` / `if layout["style"] == "split"` | Loops over each transaction and picks the column layout. | Every layout would look the same. | none |
| `Table(data, colWidths=..., repeatRows=1)` | Builds the table. `repeatRows=1` repeats the header on every page. | Pages after the first have no header. | `rowHeights`, `splitByRow`, `repeatCols`, `hAlign` |
| `TableStyle([...])` with tuples like `("GRID", (0, 0), (-1, -1), 0.25, colors.grey)` | Each tuple is a command, a start cell, an end cell (`-1` means last), then its settings. | No grid or shading; gamma and delta rely on having none. | `ALIGN`, `LINEABOVE`, `ROWBACKGROUNDS`, `SPAN` |
| `SimpleDocTemplate(path, pagesize=A4, leftMargin=40, ... title=, author=)` | Sets up a page-flowing document. Margins in points. `str(path)` converts the `Path` to text. | Content would not flow onto more pages. | `showBoundary`, `allowSplitting`, `subject`, `keywords`, `pageTemplates` |
| `doc.build(story, onFirstPage=footer, onLaterPages=footer)` | Writes the PDF. The two options say which function decorates each page. | No file is written, or no footer. | `canvasmaker` for custom page numbering |

### 4.5 Scanning, main, and writing files

| Part | What it is | What breaks without it | Other options not used |
|---|---|---|---|
| `with pdfplumber.open(path) as pdf:` | `with` guarantees the file is closed afterwards, even after an error. `as pdf` names it. | Open files pile up. | `password=` (for protected PDFs), `pages=`, `laparams=` |
| `page.extract_text() or ""` | Pulls text; `or ""` replaces an empty result (`None`) with an empty string. | `join` fails on a blank page. | `x_tolerance`, `y_tolerance`, `layout=True` |
| `"\n".join(... for page in pdf.pages)` | A generator expression feeding `join`; `\n` is a line break. | Only one page would be scanned. | none |
| `re.sub(r"/\d{12}/", "/REF/", text)` | Replaces every 12-digit run between slashes. | Real references would be reported as account numbers (this caused four false alarms, now fixed). | `count=` limits replacements; `flags=` |
| `re.search(pattern, text)` | Returns a match or `None`; used as true or false. | No scanning. | `re.findall` for all hits |
| `[label for label, pattern in ... if ...]` | A list comprehension with a filter. | You would not know which pattern fired. | none |
| `random.Random(20261111)` | A private generator with a fixed seed, so output repeats exactly. | Files and labels would change on every run and stop matching. | `random.Random()` with no seed |
| `mkdir(parents=True, exist_ok=True)` | Creates folders; `parents` creates missing parents; `exist_ok` stops an error if present. | Second run crashes. | `mode=` file permissions |
| `sorted(..., key=lambda t: t["date"])` | Sorts by the transaction date. `lambda t: ...` is a tiny unnamed function. Sorting is stable: same-day rows keep their order. | Rows would be out of date order. | `reverse=True` |
| `enumerate(rows, start=1)` | Pairs each row with a counter beginning at 1. | Labels could not point to a row number. | `start` defaults to 0 |
| `assert balance >= 0, "message"` | Stops the program with the message if the test is false. | A negative-balance statement would slip through. | the message is optional |
| `open(..., "w", newline="", encoding="utf-8")` | `"w"` writes (and overwrites). `newline=""` stops blank lines on Windows; `encoding` fixes the text format. | Extra blank lines or odd characters on some systems. | `"a"` appends, `"r"` reads, `"x"` fails if the file exists; `buffering`, `errors` |
| `csv.writer(f)`, `writerow`, `writerows` | Writes one row or many. | Commas inside values would break columns. | `delimiter=`, `quotechar=`, `lineterminator=` |
| `if __name__ == "__main__": main()` | Runs `main()` only when you run the file directly, not when another file imports it. | Importing the file would regenerate everything. | none |

## 5. How to use these in the pipeline

1. Point the T2 parser tests at `data/synthetic/`, and compare against `expected_candidates.csv` by `statement_id` and `row_number` (row 1 is the first transaction after the opening balance).
2. Put the labelled held-out split aside before tuning, as the plan says. Suggested: all of `delta` as held-out for adapter generalisation.
3. Keep `data_origin = synthetic` in every accuracy report so the real-data gate stays honest.
4. Replace this folder's files with real redacted ones as they arrive; keep the generator for edge cases you want to force.
