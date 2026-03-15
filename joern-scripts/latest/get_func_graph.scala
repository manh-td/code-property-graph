import java.nio.file.Paths
import scala.util.Try

def normalizeVariable(value: Any): Option[String] = value match {
   case null => None
   case s: String => Some(s)
   case n: java.lang.Number => Some(n.toString)
   case b: java.lang.Boolean => Some(b.toString)
   case opt: Option[_] => opt.flatMap(normalizeVariable)
   case _: scala.collection.Map[_, _] => None
   case _: java.util.Map[_, _] => None
   case other => Some(other.toString)
}

def edgeVariable(edge: Any): Option[String] = {
   val methods = edge.getClass.getMethods.toList

   // Older Joern versions exposed edge.propertiesMap.
   val fromPropertiesMap = methods
      .find(m => m.getName == "propertiesMap" && m.getParameterCount == 0)
      .flatMap { m =>
         Try(m.invoke(edge)).toOption.flatMap {
            case m: scala.collection.Map[_, _] @unchecked =>
               m.asInstanceOf[scala.collection.Map[Any, Any]].get("VARIABLE").flatMap(normalizeVariable)
            case m: java.util.Map[_, _] @unchecked =>
               normalizeVariable(m.asInstanceOf[java.util.Map[Any, Any]].get("VARIABLE"))
            case _ => None
         }
      }

   // Newer Joern versions may expose edge.property(key).
   val fromPropertyMethod = methods
      .find(m => m.getName == "property" && m.getParameterCount == 1)
      .flatMap { m =>
         Try(m.invoke(edge, "VARIABLE")).toOption match {
            case Some(opt: Option[_]) => opt.asInstanceOf[Option[Any]].flatMap(normalizeVariable)
            case Some(null)           => None
            case Some(value)          => normalizeVariable(value)
            case None                 => None
         }
      }

   fromPropertiesMap.orElse(fromPropertyMethod)
}
@main def exec(filepath: String, outputDir: String, workspaceName: String) = {
   open(workspaceName)
   run.ossdataflow

   val fileName = Paths.get(filepath).getFileName.toString
   val allowedEdgeLabels = Set("ARGUMENT", "AST", "BINDS", "CAPTURE", "CONDITION", "RECEIVER", "REF")
   cpg.all
      .flatMap(node => node.outE)
      .filter(edge => allowedEdgeLabels.contains(edge.label))
      .map(edge => List(edge.dst, edge.src, edge.label, edgeVariable(edge)))
      .toJson #> s"$outputDir/$fileName.edges.json"

   cpg.all
      .map(node => node)
      .toJson #> s"$outputDir/$fileName.nodes.json"
}