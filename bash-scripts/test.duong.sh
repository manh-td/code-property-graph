#!/bin/bash

set -euo pipefail

mkdir -p "./joern-output/latest" "./joern-output/v1.1.1298"

./joerns/latest/joern-cli/joern --script "./joern-scripts/latest/import_code.scala" --param filepath="./examples/sample.py" --param outputDir="./joern-output/latest" --param workspaceName="sample-latest"
./joerns/latest/joern-cli/joern --script "./joern-scripts/latest/get_func_graph.scala" --param filepath="./examples/sample.py" --param outputDir="./joern-output/latest" --param workspaceName="sample-latest"

./joerns/v1.1.1298/joern-cli/joern --script "./joern-scripts/v1.1.1298/import_code.scala" --params filepath=./examples/sample.py,outputDir=./joern-output/v1.1.1298,workspaceName=sample-v1.1.1298
./joerns/v1.1.1298/joern-cli/joern --script "./joern-scripts/v1.1.1298/get_func_graph.scala" --params filepath=./examples/sample.py,outputDir=./joern-output/v1.1.1298,workspaceName=sample-v1.1.1298