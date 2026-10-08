# Design: turning model policies into data, for confirmation, with no code written

The direction follows industry practice: make decision logic data rather than code. This design converts only the
parameters inside a model into framework fields; the shape of each model's algorithm, whether weighted summation,
requirement evaluation or expression evaluation, stays in code and stays unmodifiable. Every step defaults to
today's behaviour and is guarded by a field-by-field equality test.

## 1. Scope

Becoming data: a per-signal score value for partial evidence, a configurable conclusion precedence, multiplicative
threshold adjustments, and duplicating a slice together with its model and parameters. Staying in code: the
algorithm's shape, the kinds of exception, the set of logical operators and the expression whitelist. The first four
affect how strict and in what order a judgment is, which belongs to the author; the last four affect whether the
engine is explainable and auditable, which belongs to the platform.

## 2. Per-signal score value

Today a fired signal counts fully. Afterwards each signal may carry a score value, defaulting to one, so a weight of
0.35 contributes 0.35 as before unless the signal is declared partial. The score becomes the weight times the score
value times the exception factor, with only that final multiplication added. In line-by-line and whole-document entry
the same syntax applies, with an optional third segment after the dimension, for example a rule written with market
as its dimension and a value of one half. The signal panel gains a small score input defaulting to one.

## 3. Configurable conclusion precedence

The order, being combination rules then score bands then fallback, is currently fixed. It becomes a framework field
whose default reproduces today, optionally reversed so bands are consulted before rules, with unknown entries
reported by validation rather than ignored. The score band panel gains a two-option selector.

## 4. Multiplicative threshold adjustments

Adjustments can only add today. A factor becomes available, written with a multiplication sign, so that a condition
may scale the baseline rather than shift it, and additions and multiplications may be mixed in declared order.

## 5. Duplicating a slice

A button duplicates the current slice's framework, including its model, weights, thresholds, signals, rules,
formulas, boundaries, delivery and billing, into a new draft slice. Authorization rules, decision records and
confidence status are deliberately not copied, so the copy starts unenabled and unverified, named as a copy by
default, created through a duplicate endpoint.

## 6. Compatibility and acceptance

A slice without the new fields must produce a field-by-field identical package, tested directly. Validation reports
out-of-range values, unknown precedence entries and a simultaneous delta and factor, and the interface behaviour
test asserts that the new inputs exist.

## 7. Four steps, each separately verifiable

The score value, then the precedence, then the multiplicative adjustment, then duplication, each with its own
acceptance criterion and each requiring a restart.

## 8. Points to confirm

Whether the scope is right, whether the score value should be a numeric third segment or a Chinese phrasing, whether
two precedence options suffice or arbitrary ordering is needed, and whether copy is the right default name.
