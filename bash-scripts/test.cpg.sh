#!/bin/bash

joern-parse "examples/" --output "joern-output/sample.cpg.bin"
# joern-export --repr "cpg" --format dot --out "joern-output/cpg" "joern-output/sample.cpg.bin"
joern --script "scripts/graph-for-funcs.sc" \
	--param cpgFile="joern-output/sample.cpg.bin" \
	--param outFile="joern-output/sample.cpg.json"