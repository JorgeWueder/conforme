import { notFound } from "next/navigation";
import { FichaDocumentos } from "../../../../src/documentos/ficha";

export default async function Documentos({ params }) {
  const { id } = await params;
  if (!/^[1-9]\d{0,18}$/.test(id)) notFound();
  return <FichaDocumentos id={id} />;
}
