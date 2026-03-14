#!/bin/bash
mkdir -p joern-output
rm -rf joern-output/export-*

joern-parse "examples/sample.py" --output "joern-output/sample.cpg.bin"

for repr in all ast cdg cfg cpg cpg14 ddg pdg; do
	out_dir="joern-output/export-${repr}"
	joern-export --repr "${repr}" --format graphson --out "${out_dir}" "joern-output/sample.cpg.bin"
done
