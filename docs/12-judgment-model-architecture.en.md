# Judgment model architecture: separating the engine from the algorithm, for confirmation

> Status: design only, no code written. The goal is that a judgment model is not baked into the engine but is
> declarable, replaceable, versioned and auditable.

## 1. The problem, with measurements

A single 374-line module, backend/skill_framework.py, holds four things at once: the field names of the judgment
model, where signals appears seven times and combination_rules twice; the execution order from threshold through
signals, exceptions, combination rules and scoring to the fallback; the one algorithm, a single weighted sum on
line 227; and the output shaping with its tiers. Searching the file for model, registry, plugin, strategy or
scorecard finds nothing. The consequence is that supporting another kind of judgment means editing product code.

## 2. Four goals, each verifiable

A slice declares which judgment model it uses; adding a kind of judgment means adding a model file and one registry
line rather than touching the engine; every package records the model and its version so past decisions can be
reproduced; and nothing breaks, with pieces, interfaces, package fields, the call contract and audit records all
unchanged and guarded by a field-by-field equality test.

## 3. Structure

The engine holds the interface, the registry and the dispatch, and no algorithm at all. Three models sit beside it:
the scorecard that exists today, moved across unchanged; a requirements model with all-of, any-of, none-of and not,
nested as needed, which legal work needs most; and a formula model evaluating a restricted expression for domains
with a real computation, such as dosage from weight and renal function, or a discounted cash flow. The engine looks
the model up from the framework, defaulting to the scorecard, validates through the model and stamps the package
with the model and its version.

## 4. The interface

A model declares an id, a version that must rise whenever its meaning changes, labels, a sentence on where it
applies and a list of where it does not, an input contract describing the fields it needs so the interface and the
call contract can render from it, a validate step that reports every problem rather than staying silent, a pure
judge function whose identical inputs always yield an identical package, an output contract, and a reasoning step
list for explainability. The registry maps ids to models, and the default is the scorecard, so slices without a
model field behave exactly as today. Packages gain model and model version and lose nothing.

## 5. The three models

The scorecard keeps today's inputs and order, scoring by summing the weights of the dimensions whose signals fired,
with exception factors genuinely applied, and it suits accumulating evidence that lands in bands, such as credit
scorecards, underwriting, pre-operative risk grades and compliance checklists. The requirements model evaluates
rules over requirement combinations with all-of, any-of, none-of and not, taking the first matching rule in declared
order and otherwise the fallback, and it suits contract validity, limitation periods and eligibility, while it does
no weighted summing. The formula model evaluates named formulas built from a whitelist of arithmetic, min, max, abs
and round plus comparisons and boolean operators, using a small parser rather than eval, with depth and length
limits and errors located by character, then maps results through bands to conclusions; it suits dosage, cash flow
and actuarial work.

## 6. Three hard constraints

Every model must produce a reasoning path, must have no side effects, no network, no disk writes, no global state,
no eval or exec, no randomness and no reliance on the current time, and must be reproducible, so that model,
version, inputs and framework always reproduce the same package and any change in meaning raises the version.

## 7. Interfaces and the contract

The weights and score-band panels appear only under the scorecard; another model renders its own inputs from its
contract, and switching warns that validation will run again rather than silently discarding content. The call
contract gains the model and version plus that model's field list and outputs, and audit records store both.

## 8. Stating the applicable scope

The interface and documentation will say plainly that the scorecard suits accumulating evidence and not sequential
branching, requirement logic, domain formulas or probabilistic conclusions, that the requirements model suits
requirement-based judgments, and that the formula model suits domains with an explicit computation, so users choose
the right model from the start.

## 9. Four steps, each separately verifiable

First, a pure move into an engine plus the scorecard model, verified by a field-by-field equality test on the same
framework and data. Second, the model field and version, contract and interface rendering by model, and audit
recording. Third, the requirements model with nesting and negation. Fourth, the formula model with cycle detection
and positional errors. I recommend doing only the first step now, since it is invisible to users yet removes the
root problem.

## 10. Points to confirm

Whether the interface is right, whether the three model boundaries are right and whether formulas should come last,
whether field-by-field equality is an acceptable acceptance test for the first step, and whether the model field
name and the default-to-scorecard compatibility strategy are acceptable.
