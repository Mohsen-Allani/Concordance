# Samples

`native_sample.pdf` is a synthetic three-page PDF (purchase order, delivery note,
invoice) generated for demonstration. It contains no real company data.

Real supplier documents must never be committed. Put them in `samples/private/`,
which is git-ignored, and process them explicitly:

```bash
concordance run samples/private/my_scan.pdf
```
