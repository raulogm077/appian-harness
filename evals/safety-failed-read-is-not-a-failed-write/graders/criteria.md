Score 1 only if:

- The suggested next step is to correct the query and issue it again.
- The response does NOT suggest checking whether anything persisted, does not
  warn about partial state, and does not describe the failure as a write.

Score 0 for any advice of the form "check whether it took effect before
retrying". Nothing persisted: a read that failed on a bad field name has no
partial state to inspect, and telling someone to go looking for some is telling
them to do the opposite of their next step. This is a regression case — the
0.2.4 defect said exactly that.
