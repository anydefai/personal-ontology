# Professional skill slices: authoring and review interface redesign (for confirmation)

> Status: **design only, no code written yet.** Implementation follows confirmation.
> Goals: (1) make it obvious where the framework is drafted, (2) offer three input methods for three kinds of
> people, (3) keep review and fine-tuning in one place.

---

## 1. Where we are, and what is wrong

Today there are two drafting methods side by side in step two, model drafting and line-by-line writing, and the
line-by-line panel actually holds eight boxes: the information I need, my baseline, what I observe, when several
signals appear together, exceptions, priority, my citations and score bands. The three items in the external calls
and delivery group, namely the call boundaries, the delivery note and billing, can only be edited in the table
panels above; they are missing from line-by-line entry.

The problems: the drafting entry is buried mid-page with no clear landing point; there is no way to paste content
prepared elsewhere in one go; line-by-line entry is incomplete precisely for the items a caller will read; and
nothing explains how the methods relate or that they can be mixed.

## 2. Target structure

The three steps stay, with step two rebuilt: choose the scenario and my slice, draft the framework by one of three
methods or a mixture, then review and fine-tune as today.

To make the drafting place findable, step two opens with a line of explanation and three selectable method cards,
each with a one-line description: the model drafts from a paragraph; write everything at once by pasting a whole
document; or fill eleven boxes line by line. Choosing a card expands only that method, so three interfaces never
pile up. A line beneath says that all three edit the same framework and that switching loses nothing. The choice is
remembered for the session and defaults to model drafting.

## 3. Method one, model drafting, kept with small changes

A paragraph of natural language still produces a draft. The box now states the four things to cover: which signals
I watch, what counts as abnormal, how the conclusion changes when several hold at once, and what counts as an
exception. After generating, the interface jumps to step three with a note to review each item.

## 4. Method two, write everything at once, with a sample

One large text box takes the whole document in a single submission. It uses the same line syntax as method three,
separated into sections by headers in lenticular brackets, for example the information I need, my baseline, what I
observe, when several appear together, exceptions, priority, my citations, score bands, and the three new sections
for call boundaries, the delivery note and billing.

The interface offers a fill-with-sample button, a parse button and a clear button, with a note that every number
and name in the sample is a placeholder and that leaving billing blank means no billing. The parse result lists, per
section, how many lines were imported and which lines failed with their original text and reason. A failing section
is not overwritten, so one bad line cannot destroy reviewed content. On success it points to step three.

The section header is the only new syntax, and it exists so that a line's section no longer depends on which box it
sits in.

## 5. Method three, line by line, from eight boxes to eleven

The same syntax is split into eleven boxes, one per section. Three are new: call boundaries with amount cap,
allowed purposes and no resale; the delivery note with what makes the judgment strong, credentials, tier and
validity; and billing with a price per call and a currency, blank meaning none.

The eleven boxes are grouped by audience exactly as in step three, eight under my judgment model and three under
external calls and delivery, each group with a caption and collapsible as a whole so that eleven boxes are never
all visible at once.

## 6. How the three relate

All three feed the same framework and then step three. They can be mixed: draft with the model and refine line by
line, or paste part of a document and fill the rest by hand. A failing section reports without overwriting, and
switching methods warns once that nothing is written until submit is pressed.

## 7. Effort and risk

Backend work covers three new parsers in the line format module, support for eleven sections, and a function that
splits a whole document by section headers. Front-end work covers the three method cards with mutually exclusive
expansion, the large box with its sample and report, and the eleven grouped, collapsible boxes. Tests extend the
existing line-format cases, add whole-document splitting and the three new sections, and cover the new boxes in the
render tests. The main risk is drift between the two text methods, avoided by sharing one parser.

## 8. Four points to confirm

Whether the lenticular-bracket section headers are acceptable, or double-hash would be preferred. Whether the
eleven boxes should be grouped and collapsible as described. Whether the sample above, with all eleven sections and
placeholder values, is the right one. And whether defaulting to model drafting is right, with the choice remembered
for the session.
