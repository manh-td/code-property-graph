#!/bin/bash

./joerns/latest/joern-cli/joern-parse "examples/" --output "joern-output/sample.cpg.bin"
./joerns/latest/joern-cli/joern --script "joern-scripts//latestgraph-for-funcs.sc" --param cpgFile="joern-output/sample.cpg.bin" --param outFile="joern-output/sample.cpg.json"