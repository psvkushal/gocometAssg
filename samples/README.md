# Synthetic invoice fixtures

These one-page invoices contain no real shipment data. Each `.expected.json`
file records expected extracted fields and routing outcomes. Use the example
customer rules in [rules/rheintech.txt](../rules/rheintech.txt).

- `clean_invoice.pdf`: all eight fields satisfy the rules.
- `mismatch_invoice.pdf`: EXW Incoterms require an amendment.
- `missing_hs_invoice.pdf`: an absent HS code requires human review.

Live results, model comparisons, prompt experiments, timing measurements, and
limitations are maintained in [Experimentation](../docs/experimentation.md).
