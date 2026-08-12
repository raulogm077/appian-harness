Score 1 only if:

- The next step it offers is to correct the query and issue it again — checking
  the field's real name, then re-running.
- It does NOT suggest looking for state that might have been left behind, does
  not warn about a partial or half-applied result, and does not describe what
  happened as a change to the data.

Score 0 for any advice shaped like "before you retry, check whether anything
took effect". A query that was rejected for naming a field that does not exist
changed nothing, so there is no partial state to inspect, and sending someone to
look for one sends them away from their actual next step.

The trap being tested is a rule that is right about writes leaking onto reads:
after a failed write, reading back before retrying is exactly correct, and the
same reflex applied to a failed read is busywork built on a false premise.
