#!/bin/bash

mkdir -p "./joern-output/v1.1.1298"

./joerns/v1.1.1298/joern-cli/joern --script "./joern-scripts/v1.1.1298/import_code.scala" --params filepath=./examples,outputDir=./joern-output/v1.1.1298,workspaceName=sample-v1.1.1298
./joerns/v1.1.1298/joern-cli/joern --script "./joern-scripts/v1.1.1298/get_func_graph.scala" --params filepath=./examples/,outputDir=./joern-output/v1.1.1298,workspaceName=sample-v1.1.1298