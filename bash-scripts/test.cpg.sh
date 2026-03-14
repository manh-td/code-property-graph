#!/bin/bash

joern-parse "examples/" --output "joern-output/sample.cpg.bin"
joern --script "joern-scripts/graph-for-funcs.sc" --param cpgFile="joern-output/sample.cpg.bin" --param outFile="joern-output/sample.cpg.json"