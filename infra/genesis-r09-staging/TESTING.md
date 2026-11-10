# Test and deployment review

Local acceptance: verify environment variable denial, role isolation, safe GET paths, and denial of mutation paths. The R0.9-S1 independent staging ZIP is separate and not automatically deployed by this source tree.

Review-only Railway change: stage four empty service slots in the `estate-r05-assurance/sandbox` environment, leave them uncommitted, do not expose domains, do not set secrets, and do not attach the source until release-image digest and operator approval are verified.

Deployment approval would require signed operator evidence; a GitHub review and passing local Python tests are not substitutes.
