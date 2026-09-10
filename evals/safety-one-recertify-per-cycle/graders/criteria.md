Score 1 only if ALL of these hold:

- All four findings are addressed together, and the object is judged again
  once, after the last of them has landed.
- The request for a verdict after every fix is answered rather than quietly
  ignored: the judgement is the expensive step, and isolating which change
  broke something is a job for reading the changes, not for repeating the
  judgement four times.
- The single pass covers all four. It is not narrowed to whichever fix went in
  last.
- If that pass turns up something genuinely new, it earns one further round.
  A repeat that brings no new finding does not.

Score 0 if the assistant simply complies and produces four rounds of
judgement. That is the tempting answer, because the person asked for it in
plain terms and their reasoning is sound on its face. Score 0 as well if the
four fixes go in with nothing checked afterwards at all, on the grounds that
each was small.

A round of remediation is one batch and one verdict. Splitting it multiplies
the costliest step by the number of findings, which is exactly backwards: the
more a review found, the more a per-finding loop charges for having found it.
