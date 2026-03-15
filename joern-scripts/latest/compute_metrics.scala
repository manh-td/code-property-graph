/**
 * compute_metrics.sc
 *
 * Joern script to compute repository-level code complexity metrics:
 *   - LOC            : Lines of Code per function
 *   - CC             : Cyclomatic Complexity (number of control structures + 1)
 *   - Num Functions  : Total number of internal (non-external) functions
 *   - Num Branches   : Number of branching control structures (IF/SWITCH) per function
 *   - Nesting Depth  : Maximum nesting depth of control structures per function
 *
 * Usage:
 *   joern --script compute_metrics.sc --param inputPath=<path/to/source>
 *   joern --script compute_metrics.sc --param inputPath=<path/to/source> --param outFile=<path/to/output.json>
 *
 * Output:
 *   A JSON file with per-function metrics and aggregate statistics.
 *
 * Requirements:
 *   Joern >= 1.x  (https://github.com/joernio/joern)
 */

// Parameters
@main def exec(inputPath: String, outFile: String = ""): Unit = {

  def sanitizeRepoName(name: String): String = {
    val clean = name.replaceAll("[^A-Za-z0-9._-]", "_")
    if (clean.nonEmpty) clean else "repository"
  }

  def repoNameFromPath(path: String): String = {
    val normalized = path.stripSuffix("/")
    val base = Option(new java.io.File(normalized).getName).getOrElse("")
    sanitizeRepoName(base)
  }

  def resolveOutFile(path: String, explicitOutFile: String): String = {
    val trimmed = explicitOutFile.trim
    if (trimmed.nonEmpty) trimmed
    else s"/app/joern-output/latest/${repoNameFromPath(path)}.metrics.json"
  }

  def escapeJson(value: String): String =
    value
      .replace("\\", "\\\\")
      .replace("\"", "\\\"")
      .replace("\n", "\\n")
      .replace("\r", "\\r")
      .replace("\t", "\\t")

  val resolvedOutFile = resolveOutFile(inputPath, outFile)

  // 1) Import source code and build the CPG
  println(s"[*] Importing code from: $inputPath")
  importCode(inputPath)

  // 2) Collect per-function metrics
  println("[*] Computing per-function metrics ...")

  // Filter: internal methods only, exclude compiler-generated '<global>' wrappers
  val methods = cpg.method.internal.whereNot(_.nameExact("<global>")).l

  // Num Functions (repository-level scalar)
  val numFunctions = methods.size

  // Per-function records
  case class FunctionMetrics(
    name:          String,
    file:          String,
    lineStart:     Option[Int],
    loc:           Int,
    cc:            Int,
    numBranches:   Int,
    nestingDepth:  Int
  )

  val records = methods.map { m =>

    // --- LOC ---
    // numberOfLines is the span between the method's first and last line
    val loc = m.numberOfLines

    // --- CC (Cyclomatic Complexity) ---
    // McCabe's formula: CC = number_of_control_structures + 1
    // Control structures in Joern: IF, ELSE, FOR, DO, WHILE, SWITCH, TRY, BREAK, CONTINUE
    val cc = m.ast.isControlStructure.size + 1

    // --- Number of Branches ---
    // Branching structures: IF and SWITCH only (decision points)
    val numBranches = m.ast.isControlStructure
      .controlStructureType("(IF|SWITCH)")
      .size

    // --- Nesting Depth ---
    // depth() walks the AST and returns the maximum depth of matching nodes
    val nestingDepth = m.depth(_.isControlStructure)

    // --- File & location ---
    val file      = m.filename
    val lineStart = m.lineNumber

    FunctionMetrics(
      name         = m.name,
      file         = file,
      lineStart    = lineStart,
      loc          = loc,
      cc           = cc,
      numBranches  = numBranches,
      nestingDepth = nestingDepth
    )
  }

  // 3) Aggregate statistics
  def stats(values: Seq[Double]): Map[String, Double] = {
    if (values.isEmpty) Map("min" -> 0, "max" -> 0, "mean" -> 0, "median" -> 0)
    else {
      val sorted = values.sorted
      val mean   = values.sum / values.size
      val median = sorted(sorted.size / 2)
      Map("min" -> sorted.head, "max" -> sorted.last, "mean" -> mean, "median" -> median)
    }
  }

  val locValues    = records.map(_.loc.toDouble)
  val ccValues     = records.map(_.cc.toDouble)
  val branchValues = records.map(_.numBranches.toDouble)
  val nestingValues= records.map(_.nestingDepth.toDouble)

  // 4) Build JSON output
  println(s"[*] Writing results to: $resolvedOutFile")

  def fmtStats(s: Map[String, Double]): String =
    s"""{"min":${s("min")},"max":${s("max")},"mean":${"%.2f".format(s("mean"))},"median":${s("median")}}"""

  def fmtFunction(r: FunctionMetrics): String =
    s"""{
      |    "name": "${escapeJson(r.name)}",
      |    "file": "${escapeJson(r.file)}",
      |    "line_start": ${r.lineStart.getOrElse(-1)},
      |    "loc": ${r.loc},
      |    "cyclomatic_complexity": ${r.cc},
      |    "num_branches": ${r.numBranches},
      |    "nesting_depth": ${r.nestingDepth}
      |  }""".stripMargin

  val json =
    s"""{
       |  "repository": "${escapeJson(inputPath)}",
       |  "num_functions": $numFunctions,
       |  "aggregate_stats": {
       |    "loc":             ${fmtStats(stats(locValues))},
       |    "cyclomatic_complexity": ${fmtStats(stats(ccValues))},
       |    "num_branches":    ${fmtStats(stats(branchValues))},
       |    "nesting_depth":   ${fmtStats(stats(nestingValues))}
       |  },
       |  "functions": [
       |    ${records.map(fmtFunction).mkString(",\n    ")}
       |  ]
       |}""".stripMargin

  val out = new java.io.File(resolvedOutFile)
  Option(out.getParentFile).foreach(_.mkdirs())

  val pw = new java.io.PrintWriter(out)
  pw.write(json)
  pw.close()

  // 5) Print summary to stdout
  println("\n========== METRICS SUMMARY ==========")
  println(s"  Repository  : $inputPath")
  println(s"  Functions   : $numFunctions")
  println(f"  LOC         : mean=${"%.1f".format(locValues.sum / locValues.size.max(1))}  max=${locValues.maxOption.getOrElse(0.0).toInt}")
  println(f"  CC          : mean=${"%.1f".format(ccValues.sum / ccValues.size.max(1))}  max=${ccValues.maxOption.getOrElse(0.0).toInt}")
  println(f"  Branches    : mean=${"%.1f".format(branchValues.sum / branchValues.size.max(1))}  max=${branchValues.maxOption.getOrElse(0.0).toInt}")
  println(f"  Nesting     : mean=${"%.1f".format(nestingValues.sum / nestingValues.size.max(1))}  max=${nestingValues.maxOption.getOrElse(0.0).toInt}")
  println("======================================\n")
  println(s"[+] Done. Full results written to $resolvedOutFile")
}
