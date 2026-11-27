import { notFound } from "next/navigation";
import { FichaEvaluacion } from "../../../../src/evaluacion/ficha";

export default async function Evaluacion({ params }) {
  const { id } = await params;
  if (!/^[1-9]\d{0,18}$/.test(id)) notFound();
  return <FichaEvaluacion id={id} />;
}
