# Professional skill slices: page structure design v2, rewritten from your description, for confirmation

> Status: design only, no code written. Once you confirm, I will build it one block at a time and verify each
> block in the browser before showing you.

## 1. Page structure, in the order you described

Step one chooses the scenario and then my slice. A scenario is a shareable template without your judgment; a slice
is your personal judgment asset, and one scenario can have several. Below the scenario controls come my existing
slices, a box to name a new one, and a line showing the current slice with its confidence and a note that saving
and drafting both write to it. Then the list of my slices appears, one row per slice, clicking a row switching the
current slice, with a sentence instead of an empty table when there are none.

Step two creates the slice model in one of three ways: draft from the model, write everything at once, or write
line by line. Each is described in a line, and whichever one you use, saving fills step three automatically and
scrolls there.

Step three keeps review and fine-tuning exactly as today, with panels grouped by audience, a left index and
numbering.

Three differences from today: method one moves out of step one to join the other two as methods of step two; step
two gains a heading and three mutually exclusive method cards; and saving scrolls to step three. Everything else in
step one stays untouched, including scenario selection, creating, renaming and deleting scenarios, creating a
slice, the current-slice line, the slice list and the unassigned area.

## 2. The three methods

Drafting from the model suits someone who has not settled the structure; writing everything at once suits someone
who has already written it elsewhere and pastes a whole document with a sample; line-by-line writing suits someone
who thinks as they type, filling eleven boxes, seven for the model and four for the caller. The cards expand one at
a time, and a line notes that all three edit the same framework and can be switched without losing anything.

## 3. How this will be implemented, without post-render DOM surgery

The previous attempt failed because the page was rendered first and then JavaScript searched for elements and moved
them, so a wrong container silently disabled the cards and all three interfaces remained. This time the cards and
the step-two heading are written directly into the render template, the three panels are already separate functions
composed by the template according to the choice, saving reuses the existing global refresh hook and scrolls to
step three, and each block is verified on the page before being shown to you.

## 4. Four blocks, each verified separately

First, moving model drafting out of step one and adding the step-two heading. Second, the three method cards with
mutual exclusion, a remembered choice and model drafting as the default. Third, writing everything at once with a
large box, a sample and a per-section report. Fourth, line-by-line entry growing from eight boxes to eleven, seven
for the model and four for the caller, with the caller group collapsible. Finally, saving fills step three and
scrolls there.

## 5. Points to confirm

Whether this page structure is right, whether the method names should be draft from the model, write everything at
once and write line by line, and whether delivering in four separately verified blocks is acceptable.
