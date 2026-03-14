/* graph-for-funcs.scala

   This script returns a Json representation of the graph resulting in combining the
   AST, CGF, and PDG for each method contained in the currently loaded CPG.

   Input: A valid CPG
   Output: Json

   Running the Script
   ------------------
   see: README.md

   The JSON generated has the following keys:

   "functions": Array of all methods contained in the currently loaded CPG
     |_ "function": Method name as String
     |_ "id": Method id as String (String representation of the underlying Method node)
     |_ "AST": see ast-for-funcs script
     |_ "CFG": see cfg-for-funcs script
     |_ "PDG": see pdg-for-funcs script
 */

import scala.jdk.CollectionConverters._
import io.shiftleft.codepropertygraph.generated.nodes
import io.shiftleft.codepropertygraph.generated.nodes.MethodParameterIn
import ujson._

def cleanFilename(value: String): Option[String] = {
  val trimmed = Option(value).map(_.trim).getOrElse("")
  if (trimmed.isEmpty || trimmed == "N/A" || trimmed == "<empty>") None
  else Some(trimmed.stripSuffix("/"))
}

def fallbackProjectFile: Option[String] = {
  cpg.metaData.root.l.headOption.flatMap(cleanFilename)
}

def resolveMethodFile(method: nodes.Method): String = {
  val fromLocation = cleanFilename(method.location.filename)
  val fromMethodProp = cleanFilename(method.filename)
  val fromFileStep = method.file.name.l.headOption.flatMap(cleanFilename)
  val fromRawProperty = method.propertiesMap.asScala
    .get("FILENAME")
    .flatMap(value => cleanFilename(Option(value).map(_.toString).getOrElse("")))

  fromLocation
    .orElse(fromMethodProp)
    .orElse(fromFileStep)
    .orElse(fromRawProperty)
    .orElse(fallbackProjectFile)
    .getOrElse("")
}

def edgeToJson(edge: flatgraph.Edge): Value = {
  Obj(
    "id" -> Str(edge.toString),
    "in" -> Str(edge.dst.toString),
    "out" -> Str(edge.src.toString)
  )
}

def nodeToJson(node: nodes.AstNode): Value = {
  val edges =
    node.inE("AST").l ++ node.inE("CFG").l ++ node.outE("AST").l ++ node.outE("CFG").l
  val props = node.propertiesMap.asScala.toList.map { case (key, value) =>
    Obj(
      "key" -> Str(key),
      "value" -> Str(Option(value).map(_.toString).getOrElse(""))
    )
  }

  Obj(
    "id" -> Str(node.toString),
    "edges" -> Arr.from(edges.map(edgeToJson)),
    "properties" -> Arr.from(props)
  )
}

def buildGraphForFuncsJson(): Value = {
  val functions = cpg.method.map { method =>
    val methodName = method.fullName
    val methodId = method.toString
    val methodFile = resolveMethodFile(method)

    val astChildren = method.astMinusRoot.l
    val cfgChildren = method.cfgNode.l

    def sink = method.local.referencingIdentifiers.dedup
    def source = method.call.nameNot("<operator>.*").dedup

    val pdgChildren = sink
      .reachableByFlows(source)
      .l
      .flatMap { path =>
        path.elements.map {
          case trackingPoint: MethodParameterIn => trackingPoint.start.method.head
          case trackingPoint                    => trackingPoint
        }
      }
      .filter(_.toString != methodId)
      .distinct

    Obj(
      "function" -> Str(methodName),
      "file" -> Str(Option(methodFile).getOrElse("")),
      "id" -> Str(methodId),
      "AST" -> Arr.from(astChildren.map(nodeToJson)),
      "CFG" -> Arr.from(cfgChildren.map(nodeToJson)),
      "PDG" -> Arr.from(pdgChildren.map(nodeToJson))
    )
  }.l

  Obj("functions" -> Arr.from(functions))
}

@main def exec(cpgFile: String, outFile: String = ""): Unit = {
  importCpg(cpgFile)
  val payload = buildGraphForFuncsJson().render()

  if (outFile.nonEmpty) {
    payload #> outFile
  } else {
    println(payload)
  }
}
