# What someone using a professional skill in the personal ontology must be able to do

> Audience: anyone who wants to put their own professional judgment into this software and deliver it as a
> scenario slice. The short version: **no programming, no JSON and no ontology knowledge is required.** What is
> required is the judgment itself, plus the patience to break it into structured entries.

---

## 1. Overview: three tiers

| Tier | Content | Note |
|---|---|---|
| **Essential** (the task cannot be finished without it) | sections 2-6 | expressing the judgment, decomposing it, supplying numbers, required-input awareness, operating the software |
| **Useful** (improves quality) | sections 7-8 | verification habits and a maintenance mindset |
| **Not required** | section 9 | programming, JSON, ontology, databases |

---

## 2. Expressing your own professional judgment

You must be able to explain four things in plain language, because the software's first step is that you talk and
it drafts: which things you look at (signals); what counts as abnormal for each (thresholds and comparisons);
what changes when several hold at once (escalation); and which situations are exceptions (where your rule should
be softened or overridden).

> A useful rehearsal: record three minutes explaining your own process, then listen back. Wherever you struggle to
> explain it is exactly where the software will stall.

## 3. Decomposing the judgment into the software's parts

You do not need to memorise menu names, but you must be able to file each part of your judgment into the right
slot:

| Slot | The question you answer | Where it lives |
|---|---|---|
| Information I need | Which values must I have before judging? | the field list (all required) |
| Emphasis per case | How important is each dimension in different situations? | the weights table |
| My baseline | What is the baseline, and what shifts it up or down? | thresholds and adjustments |
| What I observe | How is each signal decided, and which dimension does it belong to? | the signal list |
| When several appear together | Which signals together produce which conclusion, and how severe? | combination rules |
| Exceptions | When should the rule be softened or overridden? | exception rules |
| My citations | Which authority backs each conclusion? | the citation list |
| Score bands | From which score does which conclusion follow? | score bands |
| Fallback | With nothing matching, what is the default conclusion? | fallback |

**The one structural requirement: every signal needs a dimension.** The score is the sum of the weights of the
dimensions whose signals fired, so a signal without a dimension cannot contribute. In the software this is written
as `signal ｜ dimension`.

## 4. Supplying numbers

Thresholds such as a baseline of 1.0 adjusted up by 0.2, weights expressing relative importance (0.2 / 0.2 / 0.25 /
0.35 reads well), and score bands such as "at or above 0.5 means this conclusion". **The software supplies none of
these numbers**; it only does arithmetic. The numbers come from your professional experience, and that is precisely
where the value of the asset lies.

## 5. Knowing what is genuinely required (the easiest place to come unstuck)

The software's convention is that **every field listed under information I need is required**, and that with any one
missing it will not conclude at all: it returns "insufficient information, cannot judge" and says which are missing.
So you must judge which values are the ones without which you would refuse to take a position. Too many and callers
routinely fail to supply them; too few and the judgment becomes professionally unsafe. Prefer few and hard over
comprehensive-looking.

## 6. Operating the software (a low bar)

| Step | What you do |
|---|---|
| 1 | Create principals: one for yourself as grantor, one for whoever you will deliver to |
| 2 | Create a scenario slice: describe the scenario, then draft the framework either from the model or by writing it line by line |
| 3 | Review and fine-tune each part: weights, thresholds, signals, combinations, exceptions, citations, score bands |
| 4 | Save (saving is a draft and changes nothing externally) |
| 5 | Confirm and enable, choosing the grantor and the licensee, the latter picked from approved local programs |
| 6 | Let the caller connect once, then approve it on the local-programs page with the judgment scope |
| 7 | Dry-run the scenario: omit one value and see the insufficient-information result and the highlighted field, then fill everything in and see the conclusion |

Explicitly unnecessary: programming, JSON, the command line, databases or ontology. The line-by-line format exists
for people who do not want to touch any of that: one signal per line, with `｜ dimension` at the end.

## 7. Verification habits

Turn "I believe it is right" into "I tried it". Check the required-input path by omitting one value and confirming
it refuses rather than guessing; check the boundaries with an amount above the cap or a purpose outside the allowed
range; check the normal path with data that plainly should produce a given conclusion; and check that conclusions
cite the authorities you intended, and only when the relevant signals hold.

## 8. A maintenance mindset

Treat it as an asset rather than a one-off configuration. Record why each change was made in the adjustment log;
collect the cases that were refused or judged insufficient and use them to fix fields and thresholds; and note that
confidence evolution is not implemented yet, so confidence currently has to be maintained by your own records.

## 9. What the software cannot yet do for you

| Item | Status |
|---|---|
| Billing | not implemented (a demonstration may come first) |
| Audit trail | implemented: every external judgment writes a record with conclusion, basis, caller and time |
| Automatic confidence evolution | not implemented (the adjustment log is maintained by hand) |
| Author signature | not implemented (`owner_signature` is a placeholder) |
| Caller identity | implemented: the kernel identifies the calling process, so no copyable token is involved, and only approved programs may call |
| Framework confidentiality | implemented: a caller receives the judgment, the boundaries and the status, but not the framework, the original description or the confidence rationale |

## 10. A ten-question self check

1. Can I explain my process in three minutes?
2. Can I list the fields without which I would refuse to take a position?
3. Can I give every signal a dimension?
4. Can I give relative weights between dimensions?
5. Can I state each signal's condition (field, comparison, value)?
6. Can I give an example where several signals together escalate the conclusion?
7. Can I name at least one exception?
8. Do my conclusions map to citable authorities?
9. Can I give score bands mapping scores to conclusions?
10. Am I willing to dry-run twice rather than deliver straight away?

Missing one or two is survivable, since drafts can be saved and completed gradually. The three that stall people
most often are 2, 3 and 9: they end up unable to compute a score, unable to conclude at all, or unclear where a
conclusion came from.

## 11. In one line

> This software does not ask for technical skill. It asks for clarity about your own professional judgment: seeing
> your signals, producing your numbers, stating your preconditions, recognising your exceptions and citing your
> authorities.
