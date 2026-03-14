import java.nio.file.Paths
import scala.util.Try

def edgeVariable(edge: Any): Option[Any] = {
   val methods = edge.getClass.getMethods.toList

   // Older Joern versions exposed edge.propertiesMap.
   val fromPropertiesMap = methods
      .find(m => m.getName == "propertiesMap" && m.getParameterCount == 0)
      .flatMap { m =>
         Try(m.invoke(edge)).toOption.flatMap {
            case m: scala.collection.Map[_, _] @unchecked =>
               m.asInstanceOf[scala.collection.Map[Any, Any]].get("VARIABLE")
            case m: java.util.Map[_, _] @unchecked =>
               Option(m.asInstanceOf[java.util.Map[Any, Any]].get("VARIABLE"))
            case _ => None
         }
      }

   // Newer Joern versions may expose edge.property(key).
   val fromPropertyMethod = methods
      .find(m => m.getName == "property" && m.getParameterCount == 1)
      .flatMap { m =>
         Try(m.invoke(edge, "VARIABLE")).toOption match {
            case Some(opt: Option[_]) => opt.asInstanceOf[Option[Any]]
            case Some(null)           => None
            case Some(value)          => Some(value)
            case None                 => None
         }
      }

   fromPropertiesMap.orElse(fromPropertyMethod)
}

@main def exec(filepath: String, outputDir: String, workspaceName: String): Unit = {
   open(workspaceName)
   run.ossdataflow

   val fileName = Paths.get(filepath).getFileName.toString
   cpg.all
      .flatMap(node => node.outE)
      .map(edge => List(edge.dst, edge.src, edge.label, edgeVariable(edge)))
      .toJson #> s"$outputDir/$fileName.edges.json"

   cpg.all
      .map(node => node)
      .toJson #> s"$outputDir/$fileName.nodes.json"
}