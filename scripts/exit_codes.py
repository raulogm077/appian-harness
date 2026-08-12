"""The one place the third exit code is assigned a number.

Every checker in this plugin reports three outcomes rather than two, and 3 is
the third: nothing was inspected, which is neither a pass nor a finding. Six
files typed the literal out separately -- lint_skills, n2_interface_tree,
n3_process_layout, check_evals, check_manifest_agreement and
check_package_integrity -- which is one rule written six times, the defect
hooks/test_matcher_parity.py exists to catch wearing yet another hat, and it
was committed by the same release that wrote the rule against it into
CONTRIBUTING.md.

A file of its own rather than a home in whichever checker looks senior,
because the number is also asserted in prose: CONTRIBUTING.md says
`EXIT_NOT_MEASURED = 3` and the README twice states the 0/1/2/3 scale. A copy
that drifted would leave the suite green -- each checker agreeing with itself
is the whole of what a unit test of that checker can see -- while the
documentation described a code the tree no longer returns. Nothing importable
would have noticed, which is why the parity now has a file to be about.

One constant, and deliberately nothing else. Behaviour here would make this a
module six checkers depend on for more than a value, and a shared dependency
that can take all six down at once is worth more scrutiny than a number is;
the hooks do not import it, so it does not belong in
check_package_integrity.REQUIRED_AT_RUNTIME either. Keep it a value.

    from exit_codes import EXIT_NOT_MEASURED
"""

# Distinct from 1 on purpose, and 3 rather than any other free number because
# that is what CONTRIBUTING.md and the README already tell a reader to expect.
# A run that checked nothing and a run that checked something and found
# problems are different results; collapsing them is how an absence gets read
# as a pass, and 3 is the code a caller is most likely to wave through.
EXIT_NOT_MEASURED = 3
