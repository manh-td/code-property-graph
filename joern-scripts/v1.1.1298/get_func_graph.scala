import java.nio.file.Paths
import scala.util.Try
import ujson._

def normalizeVariable(value: Any): Option[String] = value match {
   case opt: java.util.Optional[_] => if (opt.isPresent) normalizeVariable(opt.get) else None
   case opt: java.util.OptionalInt => if (opt.isPresent) Some(opt.getAsInt.toString) else None
   case opt: java.util.OptionalLong => if (opt.isPresent) Some(opt.getAsLong.toString) else None
   case opt: java.util.OptionalDouble => if (opt.isPresent) Some(opt.getAsDouble.toString) else None
   case null => None
   case s: String => Some(s)
   case n: java.lang.Number => Some(n.toString)
   case b: java.lang.Boolean => Some(b.toString)
   case opt: Option[_] => opt.flatMap(normalizeVariable)
   case _: scala.collection.Map[_, _] => None
   case _: java.util.Map[_, _] => None
   case other => Some(other.toString)
}

def invokeNoArg(target: Any, methodName: String): Option[Any] = {
   Try(target.getClass.getMethods.find(m => m.getName == methodName && m.getParameterCount == 0))
      .toOption
      .flatten
      .flatMap(m => Try(m.invoke(target)).toOption)
}

def invokeOneArg(target: Any, methodName: String, arg: Any): Option[Any] = {
   target.getClass.getMethods
      .find(m => m.getName == methodName && m.getParameterCount == 1)
      .flatMap(m => Try(m.invoke(target, arg.asInstanceOf[AnyRef])).toOption)
}

def cleanString(value: Any): Option[String] =
   normalizeVariable(value).map(_.trim).filter(v => v.nonEmpty && v != "N/A" && v != "<empty>")

def propertyValue(target: Any, key: String): Option[Any] = {
   val fromProperty = invokeOneArg(target, "property", key) match {
      case Some(opt: Option[_]) => opt.asInstanceOf[Option[Any]]
      case Some(null)           => None
      case Some(value)          => Some(value)
      case None                 => None
   }

   val fromPropertiesMap = invokeNoArg(target, "propertiesMap").flatMap {
      case m: scala.collection.Map[_, _] @unchecked =>
         m.asInstanceOf[scala.collection.Map[Any, Any]].get(key)
      case m: java.util.Map[_, _] @unchecked =>
         Option(m.asInstanceOf[java.util.Map[Any, Any]].get(key))
      case _ => None
   }

   fromProperty.orElse(fromPropertiesMap)
}

def nodeIdAsLong(node: Any): Option[Long] = {
   val rawId = invokeNoArg(node, "id").orElse(propertyValue(node, "ID"))
   rawId.flatMap {
      case n: java.lang.Number => Some(n.longValue())
      case s: String           => Try(s.toLong).toOption
      case _                   => None
   }
}

def nodeFilename(node: Any): Option[String] = {
   cleanString(invokeNoArg(node, "filename").orNull)
      .orElse(propertyValue(node, "FILENAME").flatMap(cleanString))
      .orElse(propertyValue(node, "filename").flatMap(cleanString))
      .orElse {
         invokeNoArg(node, "location")
            .flatMap(location => invokeNoArg(location, "filename"))
            .flatMap(cleanString)
      }
}

def edgeVariable(edge: Any): Option[String] = propertyValue(edge, "VARIABLE").flatMap(normalizeVariable)

def exportNode(rawNode: Value, node: Any, fallbackFilename: String, astFilenameByNodeId: Map[Long, String]): Value = {
   val idValue = nodeIdAsLong(node)
   val resolvedFilename = nodeFilename(node)
      .orElse(idValue.flatMap(astFilenameByNodeId.get))
      .orElse(cleanString(fallbackFilename))
      .getOrElse("")
   val obj = rawNode match {
      case o: Obj => o
      case _      => Obj()
   }
   obj("filename") = Str(resolvedFilename)
   obj
}

@main def exec(filepath: String, outputDir: String, workspaceName: String) = {
   open(workspaceName)
   run.ossdataflow
   val fileName = filepath.split("/").last.toString()
   val projectFilename = cleanString(invokeNoArg(cpg.metaData, "root").orNull).getOrElse("")
   val astFilenameByNodeId = cpg.method.l.flatMap { method =>
      nodeFilename(method).toList.flatMap { filename =>
         method.ast.l.flatMap(astNode => nodeIdAsLong(astNode).map(_ -> filename))
      }
   }.toMap

   cpg.graph.E
      .map(node => List(node.inNode.id, node.outNode.id, node.label, edgeVariable(node)))
      .toJson |> outputDir + "/" + fileName + ".edges.json"

   val allNodes = cpg.graph.V.l
   val rawNodes = read(cpg.graph.V.map(node => node).toJson) match {
      case arr: Arr => arr.value.toList
      case _        => List.empty[Value]
   }
   val exportedNodes = allNodes.zip(rawNodes).map {
      case (node, rawNode) => exportNode(rawNode, node, projectFilename, astFilenameByNodeId)
   }
   Arr.from(exportedNodes).render() |> outputDir + "/" + fileName + ".nodes.json"
}