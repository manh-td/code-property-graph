#!/bin/bash

mkdir -p "./joern-output/latest" "./joern-output/v1.1.1298"

./joerns/latest/joern-cli/joern --script "./joern-scripts/latest/import_code.scala" --param filepath="./examples/sample.py" --param outputDir="./joern-output/latest" --param workspaceName="sample-latest"
./joerns/latest/joern-cli/joern --script "./joern-scripts/latest/get_func_graph.scala" --param filepath="./examples/sample.py" --param outputDir="./joern-output/latest" --param workspaceName="sample-latest"
