"""The one place the third exit code is assigned a number.

The scale every checker in this plugin reports on:

    0  clean -- something was checked and found in order
    1  findings
    2  usage
    3  NOT MEASURED -- nothing was inspected; not a pass

Import it, never re-type it:

    from exit_codes import EXIT_NOT_MEASURED

Why a file of its own, and why nothing else belongs in it:
docs/design-notes.md § exit_codes.py · why a file of its own, one value, no behaviour
"""

# Distinct from 1: checking nothing and finding problems are different results.
# docs/design-notes.md § exit_codes.py · the contract
EXIT_NOT_MEASURED = 3
