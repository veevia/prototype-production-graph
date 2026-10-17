## Problem

- **Problem statement:** Reviewers re-key certificate values to compare them with the specification, which is slow and still misses out-of-spec values.
- **Job (one sentence):** When a lot arrives with its supplier certificate, confirm every result against our specification so compliant lots are released the same shift and the rest are held with a clear reason.
- **Primary persona (one sentence):** A plant QA reviewer who checks 15–20 incoming ingredient lots a shift against supplier certificates.
- **Top pain (one sentence, with evidence):** Re-keying certificate values into a spreadsheet takes a median 11 minutes per lot and still lets out-of-spec values past the first review. — E-01, E-02, E-03
- **Opportunity:** Show every certificate value next to its limit with a derived, explained verdict, so the reviewer decides on one screen without re-keying.
- **POV:** A plant QA reviewer needs to confirm a certificate against the specification without re-keying it because reviewers trust a derived verdict when they can see each value next to its limit (I-02).
- **We design against:** Auto-release with no human decision; A generic document inbox that hides the numbers

## Users

Primary: plant QA reviewers (E-01, E-11). Secondary: the QA lead (escalations, E-06) and supplier quality (notices, E-08).

