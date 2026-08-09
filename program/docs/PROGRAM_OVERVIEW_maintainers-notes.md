# Maintainer's notes — the platform documentation

Working notes for whoever edits the documentation. This is deliberately a
separate file: it is about the *documents*, not about the platform, and it was
cluttering the overview itself.

Nothing here needs to reach a reader. Delete this file if the documentation is
finished and will not be reissued.

## 0. Which file is which

| File | What it is |
|------|------------|
| `PROGRAM_PLATFORM_DOCUMENTATION.docx` | **The current document.** Four parts, sections numbered continuously 1–29 |
| `PROGRAM_OVERVIEW.docx` | The hand-merged predecessor it was built from. Kept as a backup; superseded |

The current document is assembled by script from three inputs — the predecessor's
prose, the generated inventory, and the generated figures. **Sections 18–24 and
every menu listing in section 14 are generated**, so they are not edited by hand:
change the software, re-run the scripts, and they follow.

```
python program/tools/docs/extract_inventory.py inventory.json
python program/tools/docs/extract_overview.py program/docs/PROGRAM_OVERVIEW.docx overview.json
python program/tools/docs/build_figures.py inventory.json program/docs/assets/guide/
python program/tools/docs/build_combined.py overview.json inventory.json \
       program/docs/PROGRAM_PLATFORM_DOCUMENTATION.docx
```

**After every rebuild, open the file in Word, select all (Ctrl+A) and press F9**,
choosing "update entire table" when prompted. The contents list, the figure and
screenshot lists, the running headers and the page numbers are all Word fields
and are empty until they are updated. A freshly built file looks broken until
this is done — that is expected, not a fault.

### 0.1 Structure

| Part | Sections | Divider colour |
|------|----------|----------------|
| I — Platform Overview | 1–8 | Dark navy `#1B2A4A` |
| II — User and Administration Guide | 9–17 | Blue `#1F4E8C` |
| III — Technical Reference | 18–24 | Slate grey `#444F5A` |
| IV — Supporting Information | 25–29 | Dark teal `#114B4B` |

Numbering runs continuously rather than restarting per part, so `10.4` or `14.5`
identifies a section without needing the part number. **If you add a section,
renumber in the build script rather than in Word** — every later section shifts,
and the cross-references in the prose ("see section 10", "charted in section 6")
are plain text, not fields, so they do not follow automatically. Search for
"section " after any renumbering.

Body pages are white. The four colours appear only on divider pages, headings and
small accents.

---

## 1. Screenshots

### 1.1 Why they matter

The overview is written for managers, governors and administrators who will
never run the platform themselves. For that audience prose has a hard limit: it
can describe that a dashboard exists, but not its density, legibility, or how
much work one screen does.

There is a second function. Several claims in the overview are assertions a
sceptical reader cannot check — that MFA is implemented, that the audit trail is
inspectable, that one account really spans five systems. A screenshot converts
each from a claim into evidence. The priorities below are ordered by *which
assertion most needs supporting*, not by which screen looks most impressive.

### 1.2 Slots already marked in the document

**Fifteen figures** (charts and diagrams) are present and generated — see §0.
**Ninety-one screenshot positions** are marked with bordered placeholder boxes
reading `SCREENSHOT GOES HERE`.

The boxes no longer carry hard-coded numbers: each is numbered by a Word `SEQ`
field, so inserting or deleting one renumbers the rest on the next field update,
and the screenshot list in section 26 follows. **Do not type a number into a
box** — it will not renumber and will eventually contradict the list.

Slots divide roughly as: 8 in Part I (the evaluator-facing screens), and 83 in
Part II — three per system plus one per menu category, so every menu page has a
slot.

The per-system slots that used to sit in the overview's §6 were dropped when the
documents merged: they duplicated Part II's, and Part I is meant to stay concise.
If Part I ever needs its own again, take them from section 14 rather than
capturing twice.

#### Where the slots are

The document itself carries the authoritative list — section 26, built from the
`SEQ` fields. Rather than duplicate 91 rows here, the shape is:

| Where | Slots | Covers |
|-------|-------|--------|
| Part I | 8 | Launcher, desktop dashboard, sign-in, MFA setup, a feature in use, branding, the system switcher, the API documentation page |
| Part II §9–13 | ~8 | First run, desktop regions, CLI menus, the standard record screen, superadmin dashboard, an API call end to end |
| Part II §14 | ~65 | Three per system (desktop, command line, worked task) plus one per menu category |
| Part II §15–16 | ~2 | Branding, the student journey |

Each placeholder is followed by a "What this shows" paragraph that sits
**outside** the bordered box, so it survives when the box is replaced by the
image. Each box carries its own capture instruction and target filename.

**Capturing them in one pass.** Work by interface, not by system: run all five
command lines in one sitting, then all five desktop applications, then work down
`/api/v1/docs` once with the API server running. Doing it system-by-system means
starting and stopping the app dozens of times.

**Two need care.** The first-run capture must be taken on a *clean* copy before
anything else exists, or it cannot be taken at all without starting over. The
API-call capture shows a live token — redact it before the image goes anywhere.

### 1.3 How to decide what else to capture

The test is whether the image shows something the prose cannot. A picture of a
menu adds little — a list of menu items reads fine as text. A picture of the
nursery ratio-alerts board adds a lot, because no description conveys what a live
staffing-ratio breach looks like to the person who must act on it.

Three questions settle most cases:

- Does it support a claim the reader would otherwise take on trust?
- Does it show a shape of interface not already seen elsewhere in the document?
- Would its absence leave a wrong impression — for instance, that the CLI is a
  degraded fallback rather than a full interface?

Restraint beats coverage. Every image is one more thing to retake when the
interface changes; thirty stale screenshots are less trustworthy than eight
current ones. The document marks 91 slots because Part II covers three
interfaces across five systems and gives every menu category a page — but that is
a ceiling, not a quota. Nothing breaks if a box is deleted; the rest renumber.

The Part II slots carry a different burden from the Part I ones and should be
judged differently. A Part I screenshot is evidence that a thing exists. A Part II
screenshot is an instruction: it shows the reader the screen they will be looking
at while following the steps. That makes them more valuable to someone actually operating
the platform and more damaging when stale, because a reader following a
walkthrough against a screen that no longer matches will assume they have gone
wrong rather than that the document has.

### 1.4 If only some are captured

Capturing all 91 is several days' work. If the document has to go out before
then, these carry the most weight; the rest of the boxes can be deleted without
leaving an obvious hole. They are named rather than numbered, because the numbers
now move.

**The five-system switcher** (Part I). That one account spans all five phases is
the platform's central claim and the justification for the whole architecture. It
is asserted in several places and evidenced only here. Capture mid-switch, signed
in as the superadmin demo account so all five appear.

**The API documentation page** (Part I). The document says a REST API exists.
This shows it is browsable and self-documenting at `/api/v1/docs` — the
difference between an API you must ask about and one you can evaluate on the
spot. It stands in for every per-system API slot if those are dropped.

**Any one command line.** Almost every other image shows a window. Without one
terminal image a reader assumes the CLI is cut-down, and misses that the platform
runs on a server with no graphical environment — which is how a hosted deployment
works. Capture a menu *and the result of one completed action*; a bare prompt
proves nothing.

**The nursery ratio-alerts board** (§14.1). The clearest phase-specific feature
in the platform, and the one that most needs a picture: no description conveys
what a live staffing-ratio breach looks like to the person who must act on it.

**The desktop window and its regions** (§11). The one image that pays for itself
several times over — it orients the reader for every other desktop screenshot in
the document. If the per-category slots go, keep this one.

### 1.5 Further candidates

Not yet marked in the document; add a box if one is captured.

| Image | Where | What it proves |
|-------|-------|----------------|
| A generated report or invoice | §5, Communications | Quality of *output*, which is what reaches parents |
| The audit log viewer | §4, Auditing | The trail is inspectable in-app, not just written to a file |
| A parent-portal view | §5, Additional capabilities | The only non-staff perspective available |
| The offline-sync indicator | §2, Working offline | Offline is a visible state, not a silent failure |

### 1.6 Data protection when capturing

**Use demonstration data only.** This platform holds records about children. A
screenshot showing real names, dates of birth, addresses, medical notes,
attendance patterns or safeguarding concerns is a disclosure of personal data as
much as a database export would be — and it travels further, because it is
embedded in a document that gets forwarded, printed and attached to emails long
after anyone remembers what is in it.

- **Check the edges.** A notification popup, taskbar, window title, browser tab
  or recent-files list can leak a real name into an otherwise clean image.
- **Redact rather than crop.** Cropping in some tools only hides the region; the
  original pixels can survive in the file.
- **Redact by flattening**, not by placing a shape over the image in Word — a
  shape can be dragged aside by the next person to open the document.
- **Re-check before circulation.** The person who captures and the person who
  sends are often not the same, and the second cannot tell whether the data was
  real.

### 1.7 Practical capture guidance

- Capture the window, not the whole screen.
- Keep window size consistent so images sit at a uniform scale.
- **Mind the window size**: the desktop app opens at 1400×900 with a minimum of
  1200×800, wider than a 1366px display. On a smaller screen it will be clipped —
  capture on a larger monitor if available.
- Save as **PNG, not JPEG**. Interface text compresses badly as JPEG.
- Capture at normal display scaling; high-DPI captures look soft beside others.

**Tooling note.** Screen capture is not always possible on the machine running
the app. Under Wayland-based desktops — including the Linux container on ChromeOS
— one application is deliberately prevented from reading another's pixels, so
scripted capture tools fail even though the app runs normally. Use the desktop
environment's own screenshot function instead.

### 1.8 Inserting and maintaining

Save into `docs/assets/`, then replace the whole bordered placeholder box with
the picture, leaving the `Screenshot n — …` caption above it in place: the caption
carries the `SEQ` field the screenshot list is built from, so deleting it removes
the entry from section 26. Size to the text column width (**6.5 inches**) so
images align with the figures.

Keep the "What this shows" paragraph beneath each image.

Because a rebuild regenerates the whole file, **inserted images are lost on the
next build**. Either finish the captures and stop rebuilding, or add the images
to `build_combined.py` so they survive — the same way the generated figures do.

**Upkeep:** images date faster than prose — a purely visual refresh invalidates
every screenshot while changing nothing functional. An image of an interface that
no longer exists does more damage than no image, because it silently undermines
everything else on the page.

---

## 2. Document scope and maintenance

### 2.1 What the overview is

Three books in one file, each for a different reader — an overview for someone
evaluating the platform, an operating guide for the people who run it, and a
generated endpoint reference for whoever integrates with it. Nobody is expected
to read all of it, which is what the "How to use this document" page is for.

**Part II is a step-by-step operating guide** — installation, sign-in,
navigation, everyday tasks, and a worked task per system per interface. That
changes what the file is, and two consequences follow:

- **Part II dates faster than anything else in the file except the screenshots.** It
  names menu categories and entries verbatim. Rename a category and the
  walkthrough is wrong in a way a reader will hit within a minute of following
  it — worse than a stale statistic, which merely misleads.
- **It is still not a per-feature manual.** It shows the shape of the work, not
  every field on every screen. Resist requests to grow it into one: the moment it
  tries to be exhaustive it becomes unmaintainable, and the repository
  documentation already covers that ground.

If Part II ever falls out of maintenance, cut it rather than let it drift. A guide
that no longer matches the product discredits the sections around it.

### 2.2 Outstanding gaps

Gaps that are *about the platform* — sizing, retention periods, accessibility
conformance, migration, restore procedure, support model — were folded into
**§8, "Not yet established"** in the document itself, since a reader is entitled
to see them.

What remains outstanding about the **document**:

| Missing | Why it matters |
|---------|----------------|
| Screenshots | Twenty-three slots marked and empty; the document describes an interface no reader can see |
| Deployment topology | No picture of where the software sits in an organisation's estate |
| Owner, version, review date | A reader cannot tell whether what they hold is current |
| Cost of ownership | Out of scope for a technical overview, but a decision-maker needs it from somewhere |

### 2.3 Deliberate omissions

Considered and left out on purpose — re-adding any should be a conscious
decision:

- **Feature-by-feature inventory.** Hundreds of entries, stale within a release,
  nobody finishes it. §1 and §6 carry the same information at a useful altitude.
- **Development roadmap.** Long and volatile; better read live from the
  repository. Only the documented *limitations* were drawn from it, into §8.
- **Multi-tenancy.** Scaffolding exists but holds no data, and the roadmap
  describes the design as single-tenant. Presenting it as a capability would
  overstate what is built.
- **Competitor comparison.** Cannot be done fairly from inside the project.
- **Internal code structure.** Irrelevant to the audience and dates quickly.

### 2.4 How the figures were obtained

Every count — accounts, source files, API route definitions, email templates,
languages — was measured directly from the codebase and the working database on
the date on the title page. None were taken from existing documentation or
promotional material, both of which had drifted from the code in several places.

Where the project's roadmap records a limitation, that wording was preferred over
a more flattering summary. §8 is drawn from it directly, including the statement
that the platform is not recommended for production use until its security
recommendations are implemented — a caveat the project makes about itself, which
the document would be wrong to soften.

Anything described as approximate is approximate deliberately.

### 2.5 What goes stale fastest

1. **Screenshots** — invalidated by any visual refresh.
2. **The Part II walkthrough** — it quotes menu categories and entries by name, so any
   navigation change breaks it. Re-walk it against the running app, don't proofread it.
3. **Counts and statistics** — re-measure rather than carry forward.
4. **Limitations (§8)** — first to become inaccurate once fixed, and inaccurate
   in the direction that *understates* the product, which nobody notices quickly.
5. **Version number and install commands** — change with releases.
6. **Architecture and security model** — most stable; change slowly.

### 2.6 Sensitive content review

**The default-credentials table (§3)** lists working usernames and passwords.
They are development-only, created only when a specific environment flag is set,
and the surrounding text says so firmly. They are nonetheless a list of
credentials, and documents containing one get treated more casually than the
warning deserves. *For any external audience, replace the table with a statement
that demonstration accounts exist and are documented in the repository.*

**The account statistics (§3)** — 657 accounts broken down by role — come from
the live database. Aggregate figures, no personal data, so safe in most contexts;
but they disclose the size and shape of a real installation. Useful evidence of
genuine use internally; for a public document, remove.

**The security detail (§4)** is appropriate for an evaluator and is not a
vulnerability in itself — security depending on secrecy of design is not security
— but it does hand a reader a map. Weigh against the audience.

**Section 13** shows a sign-in call with a username in it and describes exactly
how tokens are obtained. That is ordinary API documentation and fine to publish.
The risk is in the *screenshot* of an API call, which will contain a real working
token unless it is redacted. Check that image specifically before circulation.

### 2.7 Before circulating

- [ ] Replace the 91 screenshot placeholders, or remove the empty slots and their
      captions (see §1.4 for which to keep if only some are captured).
- [ ] Update all fields in Word (Ctrl+A, F9) so the contents list, figure list,
      screenshot list, running headers and page numbers populate.
- [ ] Walk Part II through against the running application — every menu path it
      names should still exist.
- [ ] Confirm the API-call image has its token redacted, if captured.
- [ ] Remove the red draft note beneath the title.
- [ ] Decide on the default-credentials table (§2.6 above).
- [ ] Decide on the live account statistics (§2.6 above).
- [ ] Re-measure any figure that has drifted since the title-page date.
- [ ] Re-check §8 against the project roadmap.
- [ ] Add an owner, version number and review date.
- [ ] Optionally replace the static contents list with a native Word table of
      contents (References → Table of Contents) to get page numbers.
- [ ] Delete this notes file if the document is finished.

---

## 3. Editing the document

**The `.docx` is a build artefact, not a source.** It is assembled by the scripts
in §0 from the predecessor document's prose, the generated inventory and the
generated figures. Editing it directly works, but the next rebuild discards those
edits — so put prose changes in `build_combined.py`, and fix generated material
by fixing the software and re-running the extractor.

The one thing that genuinely lives only in the `.docx` is Part I's prose, which
came from the original overview whose generator was lost. `extract_overview.py`
pulls it back out of `PROGRAM_OVERVIEW.docx` on each build, so **keep that file**
even though it is superseded. If it is ever deleted, Part I has to be retyped.

### 3.1 What the fields do

The contents list, figure list, screenshot list, running headers and page numbers
are Word fields, not text. They are empty in a freshly built file and populate on
Ctrl+A, F9. Consequences:

- Adding or renaming a heading no longer means editing a contents list by hand.
- Screenshot and figure numbers come from `SEQ` fields, so inserting one
  renumbers the rest. Never type a number into a placeholder box.
- The running header uses `STYLEREF` against `Heading 1` and a custom `Part
  Title` style. If the `Part Title` style is renamed or removed, the left-hand
  header goes blank.
- Cross-references in the prose ("see section 10") are **plain text**, not
  fields. They do not follow a renumbering — search for "section " after any
  structural change.

### 3.2 Scripted edits

Two things to know if you script against the file:

- Table styles are looked up by display name (`Light Grid Accent 1`,
  `Table Grid`), not by the style IDs stored in the XML.
- `python-docx` only appends to the end of the body, so new elements have to be
  moved into position afterwards with `anchor.addprevious(el)`.

Keep a copy of the file before running anything against it.

### 3.3 Figures

The charts and diagrams are generated by `build_figures.py` from the same
inventory as the reference tables, so they cannot disagree with them. The
architecture diagram is the exception — it is a pre-existing image at
`docs/assets/architecture.png` and is carried through unchanged.

Colour follows a validated palette: run the dataviz validator before changing any
of it, and note that three of the categorical hues sit below 3:1 against the
chart surface, so every mark drawn in them must carry a visible direct label.
